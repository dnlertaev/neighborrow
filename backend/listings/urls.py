from django.urls import include, path
from rest_framework.routers import SimpleRouter
from .views import ActivityListView, CategoryListView, ListingViewSet

router = SimpleRouter(trailing_slash=False)
router.register('listings', ListingViewSet, basename='listing')
urlpatterns = [path('categories', CategoryListView.as_view(), name='categories'),
               path('activity', ActivityListView.as_view(), name='activity'),
               path('', include(router.urls))]
