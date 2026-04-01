import json
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from .models import Curso, SesionClase, Asistencia, Estudiante, Anotacion, Materia
from .forms import SesionClaseForm
from django.http import JsonResponse
from django.db.models import Prefetch
from django.db.models import Max
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageOps
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys


def lista_cursos(request):
    # Buscamos las materias que tengan al menos un curso activo
    # Usamos Prefetch para traer los cursos ordenados por grado en una sola consulta rápida
    materias = Materia.objects.filter(cursos__activo=True).distinct().prefetch_related(
        Prefetch('cursos', queryset=Curso.objects.filter(activo=True).order_by('grado'))
    )
    return render(request, 'gestion/lista_cursos.html', {'materias': materias})

def abrir_clase(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)

    if request.method == 'POST':
        form = SesionClaseForm(request.POST, curso=curso) # Pasamos el curso para validar
        if form.is_valid():
            sesion = form.save(commit=False)
            sesion.curso = curso 
            # Ya NO forzamos sesion.numero_clase aquí, dejamos lo que digitó el profesor
            sesion.save()
            
            estudiantes = curso.estudiantes.filter(activo=True)
            nuevas_asistencias = [
                Asistencia(sesion=sesion, estudiante=estudiante, estado='PRESENTE') 
                for estudiante in estudiantes
            ]
            Asistencia.objects.bulk_create(nuevas_asistencias)
            
            url = reverse('gestion:tomar_asistencia', kwargs={'sesion_id': sesion.id})
            return redirect(f"{url}?nueva=true")
    else:
        # LÓGICA DE SUGERENCIA:
        ultimo_registro = SesionClase.objects.filter(curso=curso).order_by('-fecha', '-id').first()
        periodo_actual = ultimo_registro.periodo if ultimo_registro else 1
        
        max_clase = SesionClase.objects.filter(curso=curso, periodo=periodo_actual).aggregate(Max('numero_clase'))['numero_clase__max']
        clase_sugerida = (max_clase or 0) + 1
        
        # INYECTAMOS LA FECHA DE HOY COMO VALOR INICIAL
        form = SesionClaseForm(
            initial={
                'periodo': periodo_actual, 
                'fecha': timezone.now().date(), # <-- El truco está aquí
                'numero_clase': clase_sugerida
            }, 
            curso=curso
        )

    return render(request, 'gestion/abrir_clase.html', {'form': form, 'curso': curso})

# --- Tomar Asistencia ---
def tomar_asistencia(request, sesion_id):
    sesion = get_object_or_404(SesionClase, id=sesion_id)
    asistencias = sesion.asistencias.all().select_related('estudiante').order_by('estudiante__apellidos')

    if request.method == 'POST':
        for asistencia in asistencias:
            estado_key = f"estado_{asistencia.id}"
            actividad_key = f"actividad_{asistencia.id}"
            tarea_key = f"tarea_{asistencia.id}"
            foto_key = f"foto_{asistencia.id}"
            borrar_foto_key = f"borrar_foto_{asistencia.id}"
            
            # CLAVES DE NOTAS (Actividad y Tarea)
            calificacion_key = f"calificacion_{asistencia.id}"
            comentario_key = f"comentario_{asistencia.id}"
            calificacion_tarea_key = f"calificacion_tarea_{asistencia.id}"
            comentario_tarea_key = f"comentario_tarea_{asistencia.id}"

            if estado_key in request.POST:
                asistencia.estado = request.POST[estado_key]

            # Leemos si el profesor marcó los checks manualmente
            asistencia.completo_actividad = actividad_key in request.POST
            asistencia.entrego_tarea = tarea_key in request.POST

            # -----------------------------------------
            # 1. GESTIÓN DE LA FOTO DE EVIDENCIA
            # -----------------------------------------
            if borrar_foto_key in request.POST:
                asistencia.evidencia_foto = None # El vigilante borrará el archivo físico
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
                
                nombre_archivo = foto_original.name.split('.')[0] + '_opt.jpg'
                foto_comprimida = InMemoryUploadedFile(
                    output, 'ImageField', nombre_archivo, 
                    'image/jpeg', sys.getsizeof(output), None
                )
                
                asistencia.evidencia_foto = foto_comprimida
                asistencia.completo_actividad = True

            # -----------------------------------------
            # 2. LÓGICA DE NOTA: ACTIVIDAD EN CLASE
            # -----------------------------------------
            # ¡Ojo! Ahora esto está FUERA de la lógica de la foto
            val_calificacion = request.POST.get(calificacion_key, '')
            if val_calificacion.isdigit():
                nota = int(val_calificacion)
                # Forzamos entre 20 y 100, y redondeamos de 10 en 10
                asistencia.calificacion = max(20, min(100, round(nota / 10) * 10))
            else:
                asistencia.calificacion = None
                
            asistencia.comentario_actividad = request.POST.get(comentario_key, '')

            # -----------------------------------------
            # 3. LÓGICA DE NOTA: TAREA EN CASA
            # -----------------------------------------
            val_calificacion_tarea = request.POST.get(calificacion_tarea_key, '')
            if val_calificacion_tarea.isdigit():
                nota_tarea = int(val_calificacion_tarea)
                # Forzamos entre 20 y 100, y redondeamos de 10 en 10
                asistencia.calificacion_tarea = max(20, min(100, round(nota_tarea / 10) * 10))
            
            # Si le pusiste nota, sí o sí entregó la tarea.
                asistencia.entrego_tarea = True 
            else:
                asistencia.calificacion_tarea = None
                
            asistencia.comentario_tarea = request.POST.get(comentario_tarea_key, '')

            # --- LÓGICA DE NOTA: QUIZ ---
            quiz_key = f"quiz_{asistencia.id}"
            calif_quiz_key = f"calificacion_quiz_{asistencia.id}"
            coment_quiz_key = f"comentario_quiz_{asistencia.id}"

            asistencia.realizo_quiz = quiz_key in request.POST
            val_calif_quiz = request.POST.get(calif_quiz_key, '')
            
            if val_calif_quiz.isdigit():
                nota_quiz = int(val_calif_quiz)
                asistencia.calificacion_quiz = max(20, min(100, round(nota_quiz / 10) * 10))
                asistencia.realizo_quiz = True # Autocompletado inteligente
            else:
                asistencia.calificacion_quiz = None
            asistencia.comentario_quiz = request.POST.get(coment_quiz_key, '')

            # --- LÓGICA DE NOTA: EXAMEN ---
            examen_key = f"examen_{asistencia.id}"
            calif_examen_key = f"calificacion_examen_{asistencia.id}"
            coment_examen_key = f"comentario_examen_{asistencia.id}"

            asistencia.realizo_examen = examen_key in request.POST
            val_calif_examen = request.POST.get(calif_examen_key, '')
            
            if val_calif_examen.isdigit():
                nota_examen = int(val_calif_examen)
                asistencia.calificacion_examen = max(20, min(100, round(nota_examen / 10) * 10))
                asistencia.realizo_examen = True # Autocompletado inteligente
            else:
                asistencia.calificacion_examen = None
            asistencia.comentario_examen = request.POST.get(coment_examen_key, '')

            # Guardamos todos los cambios del estudiante
            asistencia.save()
        
        # Guardamos la tarea asignada a la clase en general antes de irnos
        tarea = request.POST.get('tarea_asignada', '').strip()
        sesion.tarea_asignada = tarea
        sesion.save()
        
        return redirect('gestion:reporte_curso', curso_id=sesion.curso.id)

    # --- Lógica para cargar la vista al entrar (GET) ---
    clase_anterior = SesionClase.objects.filter(
        curso=sesion.curso,
        periodo=sesion.periodo,
        numero_clase__lt=sesion.numero_clase 
    ).order_by('-numero_clase').first() 

    tarea_pendiente = None
    if clase_anterior and clase_anterior.tarea_asignada:
        tarea_pendiente = clase_anterior.tarea_asignada

    es_nueva = request.GET.get('nueva') == 'true'

    # Le inyectamos a cada estudiante su historial de anotaciones de ESTA clase específica
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
        'es_nueva': es_nueva
    })

# --- ELIMINAR LA SESIÓN ---
@require_POST
def eliminar_sesion(request, sesion_id):
    sesion = get_object_or_404(SesionClase, id=sesion_id)
    # Al eliminar la sesión, Django borrará automáticamente todas las asistencias 
    # y anotaciones ligadas a ella gracias al on_delete=models.CASCADE de los modelos.
    sesion.delete()
    return redirect('gestion:lista_cursos')

@require_POST
def guardar_anotacion(request):
    """
    Esta vista recibe los datos del modal vía JavaScript (Fetch API) 
    y guarda la anotación sin recargar la pantalla.
    """
    try:
        # Cargamos los datos JSON que envía el frontend
        data = json.loads(request.body)
        
        sesion_id = data.get('sesion_id')
        estudiante_id = data.get('estudiante_id')
        tipo = data.get('tipo')
        descripcion = data.get('descripcion')

        # Buscamos las instancias correspondientes
        sesion = SesionClase.objects.get(id=sesion_id)
        estudiante = Estudiante.objects.get(id=estudiante_id)

        # Creamos la anotación
        Anotacion.objects.create(
            sesion=sesion,
            estudiante=estudiante,
            tipo=tipo,
            descripcion=descripcion
        )

        # Devolvemos una respuesta exitosa
        return JsonResponse({'status': 'success', 'mensaje': 'Anotación guardada correctamente.'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'mensaje': str(e)}, status=400)
    
def reporte_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)
    
    # Capturamos el periodo de la URL (ej: ?periodo=2). Si no hay, por defecto es 1.
    periodo_seleccionado = int(request.GET.get('periodo', 1))

    # Filtramos las sesiones ÚNICAMENTE por el periodo seleccionado
    sesiones = list(SesionClase.objects.filter( # Importante envolver en list()
        curso=curso, 
        periodo=periodo_seleccionado
    ).prefetch_related(
        Prefetch('anotaciones', queryset=Anotacion.objects.select_related('estudiante').order_by('-fecha_creacion'))
    ).order_by('numero_clase'))
    
    total_sesiones_mes = len(sesiones)
    total_sesiones_con_actividad = sum(1 for s in sesiones if s.actividad_realizada)
    
    # Calcular qué sesiones están evaluando una tarea de la clase anterior
    total_sesiones_con_tarea = 0
    for i, sesion in enumerate(sesiones):
        # Si no es la primera clase, y la clase anterior dejó tarea...
        if i > 0 and sesiones[i-1].tarea_asignada:
            sesion.evalua_tarea = True
            total_sesiones_con_tarea += 1
        else:
            sesion.evalua_tarea = False

    estudiantes = curso.estudiantes.filter(activo=True).order_by('apellidos', 'nombres')

    asistencias_db = Asistencia.objects.filter(sesion__in=sesiones)
    diccionario_asistencias = {(a.estudiante_id, a.sesion_id): a for a in asistencias_db}

    datos_tabla = []
    for estudiante in estudiantes:
        # Renombramos la lista para que sea más claro
        fila_celdas = [] 
        total_presente = 0
        total_actividades = 0
        total_tareas = 0

        for sesion in sesiones:
            asistencia = diccionario_asistencias.get((estudiante.id, sesion.id))
            
            # Empaquetamos la asistencia junto con la sesión procesada
            fila_celdas.append({
                'asistencia': asistencia,
                'sesion': sesion
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

        # Buscamos las anotaciones exclusivas de este estudiante para las clases que estamos viendo
        anotaciones_estudiante = Anotacion.objects.filter(
            estudiante=estudiante,
            sesion__in=sesiones
        ).select_related('sesion').order_by('sesion__fecha')

        datos_tabla.append({
            'estudiante': estudiante,
            'celdas': fila_celdas, # CAMBIO 3: Pasamos las celdas empaquetadas
            'total_presente': total_presente,
            'total_actividades': total_actividades,
            'total_tareas': total_tareas,
            'porcentaje_asistencia': porcentaje_asistencia,
            'porcentaje_actividades': porcentaje_actividades,
            'porcentaje_tareas': porcentaje_tareas,
            'anotaciones': anotaciones_estudiante, 
            'total_anotaciones': anotaciones_estudiante.count(),
        })

    hay_anotaciones_mes = any(sesion.anotaciones.all() for sesion in sesiones)

    contexto = {
        'curso': curso,
        'sesiones': sesiones,
        'datos_tabla': datos_tabla,
        'periodo_seleccionado': periodo_seleccionado,
        'total_sesiones_mes': total_sesiones_mes,
        'total_sesiones_con_actividad': total_sesiones_con_actividad,
        'total_sesiones_con_tarea': total_sesiones_con_tarea, # Lo pasamos a la plantilla
        'hay_anotaciones_mes': hay_anotaciones_mes,
    }

    return render(request, 'gestion/reporte_curso.html', contexto)

@require_POST
def eliminar_anotacion(request, anotacion_id):
    anotacion = get_object_or_404(Anotacion, id=anotacion_id)
    anotacion.delete()
    return JsonResponse({'status': 'ok'})