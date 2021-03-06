from django.conf.urls import url, include
from django.contrib.auth.decorators import login_required

from board_app_creator import models, views

urlpatterns = [
    url(r'', include('social.apps.django_app.urls', namespace='social')),
    url(r'^application/?$', views.ApplicationList.as_view(queryset=models.Application.objects.all_real()), name='application-list'),
    url(r'^application/create/?$', views.ApplicationCreate.as_view(), name='application-create'),
    url(r'^application/hidden/?$', views.ApplicationList.as_view(), name='application-hidden'),
    url(r'^application/(?P<pk>\d+)/?$', views.ApplicationDetail.as_view(), name='application-detail'),
    url(r'^application/(?P<pk>\d+)/delete/?$', views.ApplicationDelete.as_view(), name='application-delete'),
    url(r'^application/(?P<pk>\d+)/ignore/?$', views.application_toggle_no_application, name='application-ignore'),
    url(r'^application/(?P<pk>\d+)/renew/?$', views.application_update_from_makefile, name='application-renew'),
    url(r'^application/(?P<pk>\d+)/update/?$', views.ApplicationUpdate.as_view(), name='application-update'),
    url(r'^board/?$', views.BoardList.as_view(queryset=models.Board.objects.all_real()), name='board-list'),
    url(r'^board/create/?$', views.BoardCreate.as_view(), name='board-create'),
    url(r'^board/hidden/?$', views.BoardList.as_view(), name='board-hidden'),
    url(r'^board/(?P<pk>\d+)/?$', views.BoardDetail.as_view(), name='board-detail'),
    url(r'^board/(?P<pk>\d+)/delete/?$', views.BoardDelete.as_view(), name='board-delete'),
    url(r'^board/(?P<pk>\d+)/ignore/?$', views.board_toggle_no_board, name='board-ignore'),
    url(r'^board/(?P<pk>\d+)/update/?$', views.BoardUpdate.as_view(), name='board-update'),
    url(r'^repository/?$', views.RepositoryList.as_view(), name='repository-list'),
    url(r'^repository/create/?$', views.RepositoryCreate.as_view(), name='repository-create'),
    url(r'^repository/(?P<pk>\d+)/?$', views.RepositoryDetail.as_view(), name='repository-detail'),
    url(r'^repository/(?P<pk>\d+)/add_application_trees/$', views.RepositoryAddApplicationTrees.as_view(), name='repository-add-application-trees'),
    url(r'^repository/(?P<pk>\d+)/delete/?$', views.RepositoryDelete.as_view(), name='repository-delete'),
    url(r'^repository/(?P<pk>\d+)/renew/?$', views.repository_update_applications_and_boards, name='repository-renew'),
    url(r'^repository/(?P<pk>\d+)/update/?$', views.RepositoryUpdate.as_view(), name='repository-update'),
]
