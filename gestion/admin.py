from django.contrib import admin
from .models import Grado, Curso, CursoMateria, Materia, Estudiante, SesionClase, Asistencia, Anotacion

@admin.register(Grado)
class GradoAdmin(admin.ModelAdmin):
    list_display = ('numero',)
    search_fields = ('numero',)

@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('grado', 'seccion', 'activo')
    list_filter = ('grado', 'activo')
    search_fields = ('grado__numero', 'seccion')

@admin.register(CursoMateria)
class CursoMateriaAdmin(admin.ModelAdmin):
    list_display = ('curso', 'materia')
    list_filter = ('curso__grado', 'materia')
    search_fields = ('curso__grado__numero', 'curso__seccion', 'materia__nombre')

@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ('nombres', 'apellidos', 'curso', 'activo')
    list_filter = ('curso', 'activo')
    search_fields = ('nombres', 'apellidos')

@admin.register(SesionClase)
class SesionClaseAdmin(admin.ModelAdmin):
    list_display = ('curso_materia', 'numero_clase', 'tema', 'fecha', 'actividad_realizada')
    list_filter = ('curso_materia__curso__grado', 'curso_materia__materia', 'fecha', 'actividad_realizada')
    search_fields = ('tema',)
    date_hierarchy = 'fecha'

@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'sesion', 'estado', 'completo_actividad')
    list_filter = ('estado', 'sesion__curso_materia__curso__grado', 'sesion__fecha')
    search_fields = ('estudiante__nombres', 'estudiante__apellidos')

@admin.register(Anotacion)
class AnotacionAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'tipo', 'sesion', 'fecha_creacion')
    list_filter = ('tipo', 'sesion__curso_materia__curso__grado')
    search_fields = ('estudiante__nombres', 'estudiante__apellidos', 'descripcion')