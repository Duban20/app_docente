from django import forms
from django.utils import timezone
from .models import SesionClase

class SesionClaseForm(forms.ModelForm):
    class Meta:
        model = SesionClase
        fields = [
            'periodo',
            'fecha',
            'numero_clase',
            'tema',
            'actividad_realizada',
            'realizo_quiz',
            'realizo_examen',
        ]
        widgets = {
            'periodo': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border'
            }),
            'fecha': forms.DateInput(format='%Y-%m-%d', attrs={
                'type': 'date',
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border'
            }),
            'numero_clase': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border'
            }),
            'tema': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.curso_materia = kwargs.pop('curso_materia', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        periodo = cleaned_data.get('periodo')
        numero_clase = cleaned_data.get('numero_clase')
        fecha = cleaned_data.get('fecha')
        hoy = timezone.now().date()

        if fecha:
            if fecha > hoy:
                self.add_error('fecha', 'No puedes registrar una clase en una fecha futura.')

            if self.curso_materia:
                clases_mismo_dia = SesionClase.objects.filter(
                    curso_materia=self.curso_materia,
                    fecha=fecha
                )
                if self.instance.pk:
                    clases_mismo_dia = clases_mismo_dia.exclude(pk=self.instance.pk)

                if clases_mismo_dia.exists():
                    self.add_error(
                        'fecha',
                        f"Ya existe una clase registrada el {fecha.strftime('%d/%m/%Y')} para esta materia en este curso."
                    )

        if self.curso_materia and periodo and numero_clase:
            existe_clase = SesionClase.objects.filter(
                curso_materia=self.curso_materia,
                periodo=periodo,
                numero_clase=numero_clase
            )
            if self.instance.pk:
                existe_clase = existe_clase.exclude(pk=self.instance.pk)

            if existe_clase.exists():
                self.add_error(
                    'numero_clase',
                    f"La clase {numero_clase} del período {periodo} ya está registrada."
                )

        return cleaned_data