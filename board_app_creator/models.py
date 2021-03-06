"""
Models for board_app_creator application.
"""
import re
from os.path import join as path_join, relpath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import pre_save, post_save

import vcs
import usb

class RepositoryManager(models.Manager):
    """
    Model manager for Repository
    """
    def get_or_create_from_path(self, path):
        """
        Get or create a repo from path
        """
        vcs_repo = vcs.get_repository(path)
        return self.get_or_create(url=vcs_repo.url, path=vcs_repo.directory)

    def get_or_create_from_url(self, url, vcs_type='git'):
        """
        Get or create a repo from URL
        """
        if url[-4:] == ".git":
            directory = re.sub(r'^.*/([^/]+)\.git$', r'\1', url)
        else:
            directory = re.sub(r'^.*/([^/]+)$', r'\1', url)
        path = path_join(settings.RIOT_REPO_BASE_PATH, directory)
        vcs_repo = vcs.get_repository(path, url=url, vcs=vcs_type)
        return self.get_or_create(url=vcs_repo.url,
                                  path=relpath(vcs_repo.directory,
                                               settings.RIOT_REPO_BASE_PATH))

class USBDeviceManager(models.Manager):
    """
    Model manager for USBDevice
    """
    def update_from_system(self):
        """
        Get all currently connected USB devices and update data base
        accordingly
        """
        Port.objects.update(usb_device=None)
        for dev in usb.get_device_list():
            device, _ = self.get_or_create(usb_id=dev.usb_id, tag=dev.tag)
            try:
                port = Port.objects.get(path=dev.device)
                port.usb_device = device
            except Port.DoesNotExist:
                port = Port(path=dev.device)
            port.save()

class BoardManager(models.Manager):
    """
    Model manager for Board
    """
    def all_real(self):
        """
        All boards that do not have the no_board flag set.
        """
        return self.filter(no_board=False)

    def hidden_shown(self):
        return self.filter(no_board=True).exists()

class ApplicationManager(models.Manager):
    """
    Model manager for Application
    """
    def all_real(self):
        """
        All applications that do not have the no_application flag set.
        """
        return self.filter(no_application=False)

    def hidden_shown(self):
        return self.filter(no_application=True).exists()

class Repository(models.Model):
    """
    A RIOT related repository
    """
    url = models.CharField(max_length=256, verbose_name="URL", unique=True,
                           blank=False, null=False)
    path = models.CharField(max_length=256, unique=True)
    default_branch = models.CharField(max_length=32, blank=False, null=False,
                                      default='master')
    vcs = models.CharField(max_length=8, choices=[('git', 'Git')], blank=False,
                           null=False, default='git', verbose_name="VCS")
    has_boards_tree = models.BooleanField(default=False, null=False,
                                       verbose_name="Has Boards tree")
    boards_tree = models.CharField(max_length=256, default=None, null=True,
                                   blank=True)
    has_cpu_tree = models.BooleanField(default=False, null=False,
                                       verbose_name="Has CPU tree")
    cpu_tree = models.CharField(max_length=256, default=None, null=True,
                                blank=True, verbose_name="CPU tree")
    is_default = models.BooleanField(default=False, null=False)

    objects = RepositoryManager()

    class Meta:
        ordering = ['-is_default', 'path']

    def __str__(self):
        return self.url

    @property
    def vcs_repo(self):
        """
        Object representing the actual repository
        """
        if not hasattr(self, '_vcs'):
            self._vcs = vcs.get_repository(self.path, self.vcs, self.url)
        return self._vcs

    def has_application_trees(self):
        return self.application_trees.exists()

    def unique_application_trees(self):
        return sorted(list(set(self.application_trees.values_list('tree_name', flat=True))))

    def update_boards(self):
        for tree in self.vcs_repo.head.get_file(self.boards_tree).trees:
            board, created = Board.objects.get_or_create(riot_name=tree.name)

            if not board.no_board:
                path = path_join(self.boards_tree, tree.name)
                board.path = path
                board.repo = self
                try:
                    board.cpu_repo = Repository.objects.get(is_default=True)
                except Repository.DoesNotExist:
                    pass
                board.save()

    def update_applications(self):
        for tree_name in self.unique_application_trees():
            for app in self.vcs_repo.head.get_file(tree_name).trees:
                abs_path = path_join(tree_name, app.name)
                makefile = path_join(abs_path, 'Makefile')
                try:
                    app_name, blacklist, whitelist = Application.get_name_and_lists_from_makefile(self, makefile)
                except Application.DoesNotExist:
                    continue
                except AssertionError:
                    continue
                appobj, created = Application.objects.get_or_create(name=app_name,
                                                                    path=abs_path)
                if created or not appobj.no_application:
                    app_tree, created = ApplicationTree.objects.get_or_create(
                        tree_name=tree_name, repo=self, application=appobj)
                    for board in Board.objects.all():
                        if board.riot_name in blacklist and board not in appobj.blacklisted_boards.all():
                            appobj.blacklisted_boards.add(board)
                        if board.riot_name in whitelist and board not in appobj.blacklisted_boards.all():
                            appobj.whitelisted_boards.add(board)

class USBDevice(models.Model):
    """
    Representation of USB devices.
    """
    tag = models.CharField(max_length=60, blank=True, null=True)
    usb_id = models.CharField(max_length=9, blank=False, null=False,
                              unique=True)

    objects = USBDeviceManager()

    def __str__(self):
        connected = " [not connected]" if not self.ports.exists() else ""
        if self.tag:
            return "{} ({}){}".format(self.usb_id, self.tag, connected)
        else:
            return "{}{}".format(self.usb_id)

class Port(models.Model):
    """
    Ports a board is connected on to this system.
    """
    path = models.CharField(max_length=20, unique=True, blank=False, null=False)
    usb_device = models.ForeignKey('USBDevice', related_name='ports', blank=True,
                                   null=True)

    def __str__(self):
        return self.path

class Board(models.Model):
    """
    A board in one of the RIOT repositories.
    """
    riot_name = models.CharField(max_length=16, unique=True, blank=False,
                                 null=False, verbose_name="RIOT name")
    repo = models.ForeignKey('Repository', related_name='boards',
                             limit_choices_to={'has_boards_tree': True},
                             verbose_name='repository', blank=True, null=True)
    cpu_repo = models.ForeignKey('Repository', related_name='cpus',
                                 limit_choices_to={'has_cpu_tree': True},
                                 verbose_name='CPU Repository', blank=True,
                                 null=True)
    usb_device= models.OneToOneField('USBDevice', related_name='board',
                                     blank=True, null=True,
                                     verbose_name="USB Device")
    prototype_jobs = models.ManyToManyField('Job', related_name='+', blank=True)
    no_board = models.BooleanField(default=False, blank=False, null=False,
                                   editable=False)

    objects = BoardManager()

    def __str__(self):
        return self.riot_name

    class Meta:
        ordering = ['riot_name']

class Application(models.Model):
    """
    A representarion of a RIOT application.
    """
    name = models.CharField(max_length=16, blank=False, null=False)
    path = models.CharField(max_length=256, default=None, null=True,
                            blank=True)
    repository = models.ManyToManyField('Repository', related_name='applications',
                                        through='ApplicationTree')
    blacklisted_boards = models.ManyToManyField('Board', blank=True,
        related_name='blacklisted_applications')
    whitelisted_boards = models.ManyToManyField('Board', blank=True,
        related_name='whitelisted_applications')
    no_application = models.BooleanField(default=False, blank=False, null=False,
                                         editable=False)

    objects = ApplicationManager()

    class Meta:
        ordering = ['name']

    @staticmethod
    def get_name_and_lists_from_makefile(repository, makefile_path):
            try:
                makefile_blob = repository.vcs_repo.head.get_file(makefile_path)
            except KeyError:
                raise Application.DoesNotExist("Application's Makefile does not exist")
            if not isinstance(makefile_blob, vcs.Blob):
                raise Application.DoesNotExist("Application's Makefile is no file")
            makefile_content = makefile_blob.read()
            app_name = ''
            blacklist = []
            whitelist = []
            next_line_blacklist = False
            next_line_whitelist = False
            for line in makefile_content.splitlines():
                if next_line_blacklist:
                    blacklist.extend(re.sub(r"\s*(.+)\s*\\?$", r'\1', line).split(' '))
                    if not line.endswith('\\'):
                        next_line_blacklist = False
                if next_line_whitelist:
                    whitelist.extend(re.sub(r"\s*(.+)\s*\\?$", r'\1', line).split(' '))
                    if not line.endswith('\\'):
                        next_line_whitelist = False
                if re.match(r".*PROJECT\s*[:?]?=\s*([^\s]+).*", line):
                    app_name = re.sub(r".*PROJECT\s*=\s*([^\s]+).*", r'\1', line)
                if re.match(r".*BOARD_BLACKLIST\s*[:?]?=\s*([^\\]+)\s*\\?$", line):
                    blacklist.extend(re.sub(r".*BOARD_BLACKLIST\s*[:?]?=\s*([^\\]+)\s*\\?$", r'\1', line).split(' '))
                    if line.endswith('\\'):
                        blacklist.pop(-1)
                        next_line_blacklist = True
                if re.match(r".*BOARD_WHITELIST\s*[:?]?=\s*([^\\]+)\s*\\?$", line):
                    whitelist.extend(re.sub(r".*BOARD_WHITELIST\s*[:?]?=\s*([^\\]+)\s*\\?$", r'\1', line).split(' '))
                    if line.endswith('\\'):
                        whitelist.pop(-1)
                        next_line_whitelist = True
            if app_name == '':
                raise AssertionError("Application name not in Makefile.")
            return app_name, blacklist, whitelist

    def update_from_makefile(self):
        if self.no_application:
            makefile_path = path_join(self.path, 'Makefile')
            app_name, blacklist, whitelist = Application.get_name_and_lists_from_makefile(self.repository, makefile_path)
            self.name = app_name
            for board in models.Board.objects.all():
                if board.riot_name in blacklist and board not in self.blacklisted_boards.all():
                    self.blacklisted_boards.add(board)
                if board.riot_name in whitelist and board not in self.blacklisted_boards.all():
                    self.whitelisted_boards.add(board)
            self.save()

class ApplicationTree(models.Model):
    """
    Transit class between Application and Repository.
    """
    repo = models.ForeignKey('Repository', related_name='application_trees')
    tree_name = models.CharField(max_length=256, null=False, blank=False)
    application = models.ForeignKey('Application', related_name='application_tree',
                                    unique=True, blank=True, null=True)

    class Meta:
        unique_together = ("repo", "tree_name", "application")

    def __str__(self):
        return self.tree_name

class Job(models.Model):
    """
    A representation of a Jenkins job.
    """
    namespace = models.IntegerField(choices=((0, 'RIOT'), (1, 'Thirdparty')),
                                    blank=False, null=False, default=0)
    name = models.CharField(max_length=64, unique=True, blank=False, null=False)
    board = models.ForeignKey('Board', related_name='boards')

    def __str__(self):
        return self.name

    @property
    def path(self):
        """
        The path to the application.
        """
        return path_join(settings.JENKINS_JOBS_PATH, self.name)

def repository_pre_save(sender, instance, raw, using, update_fields, **kwargs):
    if instance.has_boards_tree:
        error = ValidationError("{} is no tree in the repository.".format(
            instance.boards_tree))
        try:
            if not isinstance(instance.vcs_repo.head.get_file(instance.boards_tree),
                              vcs.Tree):
                raise error
        except ValueError:
            raise error

def repository_post_save(sender, instance, created, raw, using, update_fields,
                         **kwargs):
    for tree, subtrees, _ in instance.vcs_repo.head.base_tree.walk():
        tree = tree if tree == '.' else tree[2:]
        if created and instance.has_boards_tree and tree == instance.boards_tree:
            instance.update_boards()

pre_save.connect(repository_pre_save, sender=Repository)
post_save.connect(repository_post_save, sender=Repository)
