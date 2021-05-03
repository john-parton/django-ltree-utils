from django import forms


def move_node_form_factory(manager):

    class Form(forms.ModelForm):

        position = forms.ChoiceField(choices=manager.Position.choices)
        relative_to = forms.ModelChoiceField(
            queryset=manager.all(), required=False
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            if self.instance and self.instance.path:
                self.fields['relative_to'].queryset = manager.exclude(
                    **{f'{manager.path_field}__descendant_of': getattr(self.instance, manager.path_field)}
                )

                position, relative_to = manager._get_relative_position(self.instance)

                self.fields['position'].initial = position
                self.fields['relative_to'].initial = relative_to

        class Meta:
            model = manager.model
            exclude = [manager.path_field]

        def clean(self, *args, **kwargs):
            cleaned_data = super().clean(*args, **kwargs)

            position = cleaned_data['position']
            relative_to = True if manager.Position(position) == manager.Position.ROOT else cleaned_data['relative_to']

            moves = manager._resolve_position(
                self.instance, {
                    position: relative_to
                }
            )

            self.cleaned_data['_moves'] = moves

        def save(self, *args, **kwargs):

            manager._bulk_move(self.cleaned_data['_moves'])

            return super().save(*args, **kwargs)

    return Form
