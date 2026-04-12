from django.urls import path
from . import views

app_name = 'gestion'

urlpatterns = [
    path('', views.lista_cursos, name='lista_cursos'),
    path('curso-materia/<int:curso_materia_id>/abrir-clase/', views.abrir_clase, name='abrir_clase'),
    path('sesion/<int:sesion_id>/asistencia/', views.tomar_asistencia, name='tomar_asistencia'),
    path('api/guardar-anotacion/', views.guardar_anotacion, name='guardar_anotacion'),
    path('curso-materia/<int:curso_materia_id>/reportes/', views.reporte_curso, name='reporte_curso'),
    path('sesion/<int:sesion_id>/eliminar/', views.eliminar_sesion, name='eliminar_sesion'),
    path('anotacion/eliminar/<int:anotacion_id>/', views.eliminar_anotacion, name='eliminar_anotacion'),
    path('estudiante/crear/', views.crear_estudiante, name='crear_estudiante'),
    path('estudiante/editar/<int:estudiante_id>/', views.editar_estudiante, name='editar_estudiante'),
    path('estudiante/inactivar/<int:estudiante_id>/', views.inactivar_estudiante, name='inactivar_estudiante'),
]