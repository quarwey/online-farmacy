from django import forms
from .models import UserAccount, Recipe, Pharmacy


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput, min_length=8)
    password2 = forms.CharField(label="Повторите пароль", widget=forms.PasswordInput)

    class Meta:
        model = UserAccount
        fields = ["name", "phone", "email"]
        labels = {"name": "Имя", "phone": "Номер телефона", "email": "Электронная почта"}

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") and cleaned.get("password2") and cleaned["password1"] != cleaned["password2"]:
            self.add_error("password2", "Пароли не совпадают.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = "Покупатель"
        user.setpass(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    phone = forms.CharField(label="Номер телефона")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)
    remember = forms.BooleanField(label="Запомнить меня", required=False)


class RecipeUploadForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ["file"]
        labels = {"file": "Файл рецепта"}
        widgets = {"file": forms.ClearableFileInput(attrs={"accept": ".jpg,.jpeg,.png,.pdf"})}

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        allowed = [".jpg", ".jpeg", ".png", ".pdf"]
        import os
        if os.path.splitext(uploaded.name)[1].lower() not in allowed:
            raise forms.ValidationError("Разрешены файлы JPG, PNG и PDF.")
        if uploaded.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Размер файла не должен превышать 10 МБ.")
        return uploaded


class CheckoutForm(forms.Form):
    pharmacy = forms.ModelChoiceField(queryset=Pharmacy.objects.all(), label="Аптека")
    delivery_method = forms.ChoiceField(choices=[("Самовывоз", "Самовывоз"), ("Доставка", "Доставка")], label="Способ получения")
    delivery_address = forms.CharField(label="Адрес доставки", required=False)
    comment = forms.CharField(label="Комментарий", required=False, widget=forms.Textarea)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("delivery_method") == "Доставка" and not cleaned.get("delivery_address"):
            self.add_error("delivery_address", "Укажите адрес доставки.")
        return cleaned
