from django import forms



def move_node_form_factory(manager):


    class Form(forms.ModelForm):

        position = forms.ChoiceField(choices=manager.Position.choices)
        relative_to = forms.ModelChoiceField(
            queryset=manager.all(), required=False
        )

        def _reverse_relative(self):
            try:
                next_sibling = manager.filter(
                    **{f'{manager.path_field}__sibling_of': self.instance.path},
                    **{f'{manager.path_field}__gt': self.instance.path}
                ).order_by(manager.path_field)[0]

                return manager.Position.BEFORE, next_sibling

            except IndexError:
                pass

            try:
                parent = manager.filter(
                    **{f'{manager.path_field}__parent_of': self.instance.path}
                ).get()

                return manager.Position.LAST_CHILD, parent

            except manager.model.DoesNotExist:
                pass

            return manager.Position.ROOT, None

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            if self.instance and self.instance.path:
                self.fields['relative_to'].queryset = manager.exclude(
                    **{f'{manager.path_field}__descendant_of': self.instance.path}
                )

                position, relative_to = self._reverse_relative()

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
