import json
import sys
from io import BytesIO

from PIL import Image, ImageOps

from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Prefetch, Max
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import InMemoryUploadedFile

from .models import Curso, CursoMateria, SesionClase, Asistencia, Estudiante, Anotacion
from .forms import SesionClaseForm


def lista_cursos(request):
    """
    Lista los cursos activos y sus materias asociadas.
    Ahora el curso representa la sección (ej: 3-01) y las materias van por CursoMateria.
    """
    cursos = (
        Curso.objects.filter(activo=True)
        .select_related('grado')
        .prefetch_related(
            Prefetch(
                'curso_materias',
                queryset=CursoMateria.objects.select_related('materia').order_by('materia__nombre')
            )
        )
        .order_by('grado__numero', 'seccion')
    )

    return render(request, 'gestion/lista_cursos.html', {'cursos': cursos})


def abrir_clase(request, curso_materia_id):
    """
    Abre una clase para una materia específica dentro de un curso.
    Antes recibía curso_id; ahora recibe curso_materia_id.
    """
    curso_materia = get_object_or_404(
        CursoMateria.objects.select_related('curso', 'materia', 'curso__grado'),
        id=curso_materia_id
    )

    if request.method == 'POST':
        form = SesionClaseForm(request.POST, curso_materia=curso_materia)
        if form.is_valid():
            sesion = form.save(commit=False)
            sesion.curso_materia = curso_materia
            sesion.save()

            estudiantes = curso_materia.curso.estudiantes.filter(activo=True)
            nuevas_asistencias = [
                Asistencia(sesion=sesion, estudiante=estudiante, estado='PRESENTE')
                for estudiante in estudiantes
            ]
            Asistencia.objects.bulk_create(nuevas_asistencias)

            url = reverse('gestion:tomar_asistencia', kwargs={'sesion_id': sesion.id})
            return redirect(f"{url}?nueva=true")
    else:
        ultimo_registro = (
            SesionClase.objects.filter(curso_materia=curso_materia)
            .order_by('-fecha', '-id')
            .first()
        )
        periodo_actual = ultimo_registro.periodo if ultimo_registro else 1

        max_clase = (
            SesionClase.objects.filter(
                curso_materia=curso_materia,
                periodo=periodo_actual
            ).aggregate(Max('numero_clase'))['numero_clase__max']
        )
        clase_sugerida = (max_clase or 0) + 1

        form = SesionClaseForm(
            initial={
                'periodo': periodo_actual,
                'fecha': timezone.now().date(),
                'numero_clase': clase_sugerida,
            },
            curso_materia=curso_materia
        )

    return render(
        request,
        'gestion/abrir_clase.html',
        {'form': form, 'curso_materia': curso_materia}
    )


def tomar_asistencia(request, sesion_id):
    """
    Toma asistencia de una sesión ya creada.
    """
    sesion = get_object_or_404(
        SesionClase.objects.select_related(
            'curso_materia__curso',
            'curso_materia__materia',
            'curso_materia__curso__grado',
        ),
        id=sesion_id
    )

    asistencias = (
        sesion.asistencias
        .filter(estudiante__activo=True)
        .select_related('estudiante')
        .order_by('estudiante__apellidos', 'estudiante__nombres')
    )

    if request.method == 'POST':
        for asistencia in asistencias:
            estado_key = f"estado_{asistencia.id}"
            actividad_key = f"actividad_{asistencia.id}"
            tarea_key = f"tarea_{asistencia.id}"
            foto_key = f"foto_{asistencia.id}"
            borrar_foto_key = f"borrar_foto_{asistencia.id}"

            calificacion_key = f"calificacion_{asistencia.id}"
            comentario_key = f"comentario_{asistencia.id}"
            calificacion_tarea_key = f"calificacion_tarea_{asistencia.id}"
            comentario_tarea_key = f"comentario_tarea_{asistencia.id}"

            if estado_key in request.POST:
                asistencia.estado = request.POST[estado_key]

            asistencia.completo_actividad = actividad_key in request.POST
            asistencia.entrego_tarea = tarea_key in request.POST

            if borrar_foto_key in request.POST:
                asistencia.evidencia_foto = None
            elif foto_key in request.FILES:
                foto_original = request.FILES[foto_key]
                img = Image.open(foto_original)
                img = ImageOps.exif_transpose(img)

                if img.mode != 'RGB':
                    img = img.convert('RGB')

                img.thumbnail((1920, 1920))

                output = BytesIO()
                img.save(output, format='JPEG', quality=85)
                output.seek(0)

                nombre_archivo = foto_original.name.rsplit('.', 1)[0] + '_opt.jpg'
                foto_comprimida = InMemoryUploadedFile(
                    output,
                    'ImageField',
                    nombre_archivo,
                    'image/jpeg',
                    sys.getsizeof(output),
                    None
                )

                asistencia.evidencia_foto = foto_comprimida
                asistencia.completo_actividad = True

            val_calificacion = request.POST.get(calificacion_key, '')
            if val_calificacion.isdigit():
                nota = int(val_calificacion)
                asistencia.calificacion = max(20, min(100, nota))
            else:
                asistencia.calificacion = None

            asistencia.comentario_actividad = request.POST.get(comentario_key, '')

            val_calificacion_tarea = request.POST.get(calificacion_tarea_key, '')
            if val_calificacion_tarea.isdigit():
                nota_tarea = int(val_calificacion_tarea)
                asistencia.calificacion_tarea = max(20, min(100, nota_tarea))
                asistencia.entrego_tarea = True
            else:
                asistencia.calificacion_tarea = None

            asistencia.comentario_tarea = request.POST.get(comentario_tarea_key, '')

            quiz_key = f"quiz_{asistencia.id}"
            calif_quiz_key = f"calificacion_quiz_{asistencia.id}"
            coment_quiz_key = f"comentario_quiz_{asistencia.id}"

            asistencia.realizo_quiz = quiz_key in request.POST
            val_calif_quiz = request.POST.get(calif_quiz_key, '')
            if val_calif_quiz.isdigit():
                nota_quiz = int(val_calif_quiz)
                asistencia.calificacion_quiz = max(20, min(100, nota_quiz))
                asistencia.realizo_quiz = True
            else:
                asistencia.calificacion_quiz = None

            asistencia.comentario_quiz = request.POST.get(coment_quiz_key, '')

            examen_key = f"examen_{asistencia.id}"
            calif_examen_key = f"calificacion_examen_{asistencia.id}"
            coment_examen_key = f"comentario_examen_{asistencia.id}"

            asistencia.realizo_examen = examen_key in request.POST
            val_calif_examen = request.POST.get(calif_examen_key, '')
            if val_calif_examen.isdigit():
                nota_examen = int(val_calif_examen)
                asistencia.calificacion_examen = max(20, min(100, nota_examen))
                asistencia.realizo_examen = True
            else:
                asistencia.calificacion_examen = None

            asistencia.comentario_examen = request.POST.get(coment_examen_key, '')

            asistencia.save()

        tarea = request.POST.get('tarea_asignada', '').strip()
        sesion.tarea_asignada = tarea
        sesion.save()

        return redirect('gestion:reporte_curso', curso_materia_id=sesion.curso_materia.id)

    clase_anterior = (
        SesionClase.objects.filter(
            curso_materia=sesion.curso_materia,
            periodo=sesion.periodo,
            numero_clase__lt=sesion.numero_clase
        )
        .order_by('-numero_clase')
        .first()
    )

    tarea_pendiente = clase_anterior.tarea_asignada if clase_anterior and clase_anterior.tarea_asignada else None
    es_nueva = request.GET.get('nueva') == 'true'

    for asistencia in asistencias:
        asistencia.anotaciones_clase = Anotacion.objects.filter(
            sesion=sesion,
            estudiante=asistencia.estudiante
        ).order_by('-fecha_creacion')

    return render(request, 'gestion/tomar_asistencia.html', {
        'sesion': sesion,
        'asistencias': asistencias,
        'tarea_pendiente': tarea_pendiente,
        'clase_anterior': clase_anterior,
        'mostrar_popup': es_nueva,
        'es_nueva': es_nueva,
    })


@require_POST
def eliminar_sesion(request, sesion_id):
    """
    Elimina una sesión y, por cascada, sus asistencias y anotaciones.
    """
    sesion = get_object_or_404(SesionClase, id=sesion_id)
    sesion.delete()
    return redirect('gestion:lista_cursos')


@require_POST
def guardar_anotacion(request):
    """
    Recibe los datos desde JavaScript y guarda una anotación.
    """
    try:
        data = json.loads(request.body)

        sesion_id = data.get('sesion_id')
        estudiante_id = data.get('estudiante_id')
        tipo = data.get('tipo')
        descripcion = data.get('descripcion')

        sesion = get_object_or_404(SesionClase, id=sesion_id)
        estudiante = get_object_or_404(Estudiante, id=estudiante_id)

        Anotacion.objects.create(
            sesion=sesion,
            estudiante=estudiante,
            tipo=tipo,
            descripcion=descripcion
        )

        return JsonResponse({
            'status': 'success',
            'mensaje': 'Anotación guardada correctamente.'
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'mensaje': str(e)
        }, status=400)


def reporte_curso(request, curso_materia_id):
    """
    Reporte de una materia dentro de un curso.
    Antes era por curso_id; ahora debe ser por curso_materia_id.
    """
    curso_materia = get_object_or_404(
        CursoMateria.objects.select_related('curso', 'materia', 'curso__grado'),
        id=curso_materia_id
    )

    curso = curso_materia.curso
    materia = curso_materia.materia

    periodo_seleccionado = int(request.GET.get('periodo', 1))

    sesiones = list(
        SesionClase.objects.filter(
            curso_materia=curso_materia,
            periodo=periodo_seleccionado
        )
        .prefetch_related(
            Prefetch(
                'anotaciones',
                queryset=Anotacion.objects.select_related('estudiante').order_by('-fecha_creacion')
            )
        )
        .order_by('numero_clase')
    )

    total_sesiones_mes = len(sesiones)
    total_sesiones_con_actividad = sum(1 for s in sesiones if s.actividad_realizada)

    total_sesiones_con_tarea = 0
    for i, sesion in enumerate(sesiones):
        if i > 0 and sesiones[i - 1].tarea_asignada:
            sesion.evalua_tarea = True
            total_sesiones_con_tarea += 1
        else:
            sesion.evalua_tarea = False

    estudiantes = curso.estudiantes.filter(activo=True).order_by('apellidos', 'nombres')

    asistencias_db = Asistencia.objects.filter(sesion__in=sesiones)
    diccionario_asistencias = {(a.estudiante_id, a.sesion_id): a for a in asistencias_db}

    datos_tabla = []
    for estudiante in estudiantes:
        fila_celdas = []
        total_presente = 0
        total_actividades = 0
        total_tareas = 0

        for sesion in sesiones:
            asistencia = diccionario_asistencias.get((estudiante.id, sesion.id))

            fila_celdas.append({
                'asistencia': asistencia,
                'sesion': sesion,
            })

            if asistencia:
                if asistencia.estado == 'PRESENTE':
                    total_presente += 1
                if asistencia.completo_actividad:
                    total_actividades += 1
                if sesion.evalua_tarea and asistencia.entrego_tarea:
                    total_tareas += 1

        porcentaje_asistencia = round((total_presente / total_sesiones_mes) * 100) if total_sesiones_mes > 0 else 0
        porcentaje_actividades = round((total_actividades / total_sesiones_con_actividad) * 100) if total_sesiones_con_actividad > 0 else 0
        porcentaje_tareas = round((total_tareas / total_sesiones_con_tarea) * 100) if total_sesiones_con_tarea > 0 else 0

        anotaciones_estudiante = (
            Anotacion.objects.filter(
                estudiante=estudiante,
                sesion__in=sesiones
            )
            .select_related('sesion')
            .order_by('sesion__fecha')
        )

        datos_tabla.append({
            'estudiante': estudiante,
            'celdas': fila_celdas,
            'total_presente': total_presente,
            'total_actividades': total_actividades,
            'total_tareas': total_tareas,
            'porcentaje_asistencia': porcentaje_asistencia,
            'porcentaje_actividades': porcentaje_actividades,
            'porcentaje_tareas': porcentaje_tareas,
            'anotaciones': anotaciones_estudiante,
            'total_anotaciones': anotaciones_estudiante.count(),
        })

    hay_anotaciones_mes = any(sesion.anotaciones.exists() for sesion in sesiones)

    contexto = {
        'curso_materia': curso_materia,
        'curso': curso,
        'materia': materia,
        'sesiones': sesiones,
        'datos_tabla': datos_tabla,
        'periodo_seleccionado': periodo_seleccionado,
        'total_sesiones_mes': total_sesiones_mes,
        'total_sesiones_con_actividad': total_sesiones_con_actividad,
        'total_sesiones_con_tarea': total_sesiones_con_tarea,
        'hay_anotaciones_mes': hay_anotaciones_mes,
    }

    return render(request, 'gestion/reporte_curso.html', contexto)


@require_POST
def eliminar_anotacion(request, anotacion_id):
    anotacion = get_object_or_404(Anotacion, id=anotacion_id)
    anotacion.delete()
    return JsonResponse({'status': 'ok'})

@require_POST
def crear_estudiante(request):
    data = json.loads(request.body)

    estudiante = Estudiante.objects.create(
        nombres=data['nombres'],
        apellidos=data['apellidos'],
        curso_id=data['curso_id'],
        activo=True
    )

    return JsonResponse({'status': 'ok'})

@require_POST
def editar_estudiante(request, estudiante_id):
    data = json.loads(request.body)

    estudiante = get_object_or_404(Estudiante, id=estudiante_id)

    estudiante.nombres = data['nombres']
    estudiante.apellidos = data['apellidos']

    estudiante.save()

    return JsonResponse({'status': 'ok'})

@require_POST
def inactivar_estudiante(request, estudiante_id):
    estudiante = get_object_or_404(Estudiante, id=estudiante_id)
    estudiante.activo = False
    estudiante.save()

    return JsonResponse({'status': 'ok'})