from django.db import models
from django.utils import timezone
from django.db.models.signals import post_delete, pre_save, post_save
from django.dispatch import receiver
import os

class Materia(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre
    
class Grado(models.Model):
    numero = models.PositiveIntegerField(unique=True)

    class Meta:
        ordering = ['numero']

    def __str__(self):
        return f"{self.numero}°"
    
class Curso(models.Model):
    grado = models.ForeignKey(Grado, on_delete=models.CASCADE, related_name='cursos')
    seccion = models.CharField(max_length=10, blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        unique_together = ['grado', 'seccion']

    def __str__(self):
        if self.seccion:
            return f"{self.grado.numero}-{self.seccion}"
        return f"{self.grado.numero}"
    
class CursoMateria(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='curso_materias')
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='curso_materias')

    class Meta:
        unique_together = ['curso', 'materia']

    def __str__(self):
        return f"{self.curso} - {self.materia}"

class Estudiante(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='estudiantes')
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    foto = models.ImageField(upload_to='fotos_estudiantes/', blank=True, null=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"

class SesionClase(models.Model):
    PERIODOS = [
        (1, 'Primer Periodo'),
        (2, 'Segundo Periodo'),
        (3, 'Tercer Periodo'),
        (4, 'Cuarto Periodo'),
    ]

    curso_materia = models.ForeignKey(
        CursoMateria,
        on_delete=models.CASCADE,
        related_name='sesiones'
    )
    periodo = models.IntegerField(choices=PERIODOS, default=1)
    fecha = models.DateField(default=timezone.now)
    numero_clase = models.PositiveIntegerField(
        help_text="Número de la clase en el periodo/año"
    )
    tema = models.CharField(max_length=255)
    actividad_realizada = models.BooleanField(default=False)
    tarea_asignada = models.TextField(blank=True, null=True)
    realizo_quiz = models.BooleanField(default=False)
    realizo_examen = models.BooleanField(default=False)

    class Meta:
        ordering = ['-fecha']
        unique_together = ['curso_materia', 'periodo', 'numero_clase']

    def __str__(self):
        return f"{self.curso_materia} - Clase {self.numero_clase} ({self.fecha})"

class Asistencia(models.Model):
    ESTADOS_ASISTENCIA = [
        ('PRESENTE', 'Presente'),
        ('AUSENTE', 'Ausente'),
        ('EXCUSADO', 'Tiene Excusa'),
    ]

    sesion = models.ForeignKey(SesionClase, on_delete=models.CASCADE, related_name='asistencias')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='historial_asistencia')
    estado = models.CharField(max_length=10, choices=ESTADOS_ASISTENCIA, default='PRESENTE')
    motivo_excusa = models.TextField(blank=True, null=True, help_text="Opcional: Por qué faltó")
    entrego_tarea = models.BooleanField(default=False)
    evidencia_foto = models.ImageField(upload_to='evidencias/%Y/%m/', blank=True, null=True)
    completo_actividad = models.BooleanField(default=False)
    # ACTIVIDAD
    calificacion = models.IntegerField(null=True, blank=True)
    comentario_actividad = models.TextField(null=True, blank=True)
    # TAREA
    calificacion_tarea = models.IntegerField(null=True, blank=True)
    comentario_tarea = models.TextField(null=True, blank=True)
    # QUIZ
    realizo_quiz = models.BooleanField(default=False)
    calificacion_quiz = models.IntegerField(null=True, blank=True)
    comentario_quiz = models.TextField(null=True, blank=True)
    # EXAMEN
    realizo_examen = models.BooleanField(default=False)
    calificacion_examen = models.IntegerField(null=True, blank=True)
    comentario_examen = models.TextField(null=True, blank=True)

    class Meta:
        # Evita que un estudiante tenga dos registros de asistencia en la misma clase
        unique_together = ['sesion', 'estudiante']

    def __str__(self):
        return f"{self.estudiante} - {self.estado} - {self.sesion.fecha}"

class Anotacion(models.Model):
    TIPO_ANOTACION = [
        ('COMPORTAMIENTO', 'Comportamiento (Positivo/Negativo)'),
        ('MATERIALES', 'Falta de materiales'),
        ('PARTICIPACION', 'Participación destacada'),
        ('OTRO', 'Otro'),
    ]

    sesion = models.ForeignKey(SesionClase, on_delete=models.CASCADE, related_name='anotaciones')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='anotaciones')
    tipo = models.CharField(max_length=20, choices=TIPO_ANOTACION, default='OTRO')
    descripcion = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Anotación: {self.estudiante} ({self.get_tipo_display()})"


# 1. Vigilante para borrado de clase o estudiante
@receiver(post_delete, sender=Asistencia)
def auto_eliminar_foto_al_borrar(sender, instance, **kwargs):
    """Borra el archivo físico del disco cuando se elimina el registro de asistencia."""
    if instance.evidencia_foto:
        if os.path.isfile(instance.evidencia_foto.path):
            os.remove(instance.evidencia_foto.path)

# 2. Vigilante para cuando reemplazas o eliminas la foto en una edición
@receiver(pre_save, sender=Asistencia)
def auto_eliminar_foto_al_modificar(sender, instance, **kwargs):
    """Borra el archivo viejo del disco si el profe sube una foto nueva o la quita."""
    if not instance.pk:
        return False

    try:
        vieja_asistencia = Asistencia.objects.get(pk=instance.pk)
        vieja_foto = vieja_asistencia.evidencia_foto
    except Asistencia.DoesNotExist:
        return False

    nueva_foto = instance.evidencia_foto
    if vieja_foto and vieja_foto != nueva_foto:
        if os.path.isfile(vieja_foto.path):
            os.remove(vieja_foto.path)

# 3. Crear asistencias para nuevo alumno agregado
@receiver(post_save, sender=Estudiante)
def crear_asistencias_para_nuevo_estudiante(sender, instance, created, **kwargs):
    """
    Cuando se crea un estudiante nuevo, se le crean asistencias
    para TODAS las clases ya existentes de su curso.
    """
    if created and instance.activo:
        # Buscar todas las sesiones del curso del estudiante
        sesiones = SesionClase.objects.filter(
            curso_materia__curso=instance.curso
        )

        nuevas_asistencias = []

        for sesion in sesiones:
            nuevas_asistencias.append(
                Asistencia(
                    sesion=sesion,
                    estudiante=instance,
                    estado='AUSENTE' 
                )
            )

        Asistencia.objects.bulk_create(nuevas_asistencias)