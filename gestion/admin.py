from django.contrib import admin
from .models import Curso, Estudiante, SesionClase, Asistencia, Anotacion, Materia

@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('materia', 'grado', 'activo')
    list_filter = ('materia', 'activo')
    search_fields = ('materia__nombre', 'grado')

@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ('nombres', 'apellidos', 'curso', 'activo')
    list_filter = ('curso', 'activo')
    search_fields = ('nombres', 'apellidos')

@admin.register(SesionClase)
class SesionClaseAdmin(admin.ModelAdmin):
    list_display = ('curso', 'numero_clase', 'tema', 'fecha', 'actividad_realizada')
    list_filter = ('curso', 'fecha', 'actividad_realizada')
    search_fields = ('tema',)
    date_hierarchy = 'fecha' # Agrega una barra de navegación por fechas muy útil

@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'sesion', 'estado', 'completo_actividad')
    list_filter = ('estado', 'sesion__curso', 'sesion__fecha')
    search_fields = ('estudiante__nombres', 'estudiante__apellidos')

@admin.register(Anotacion)
class AnotacionAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'tipo', 'sesion', 'fecha_creacion')
    list_filter = ('tipo', 'sesion__curso')
    search_fields = ('estudiante__nombres', 'estudiante__apellidos', 'descripcion')