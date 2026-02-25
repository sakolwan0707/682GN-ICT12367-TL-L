from django.urls import path
from myapp import views
app_name = "myapp"

urlpatterns = [
    path('', views.index, name="index"),
    path('about', views.about, name="about"),
    path('form/', views.form, name="form"),
    path('contact', views.contact, name="contact"),
]