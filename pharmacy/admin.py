from django import forms
from django.contrib import admin
from django.contrib.auth.hashers import make_password

from .models import (
    UserAccount, Manufacturer, ReleaseForm, Pharmacy, Medicine,
    Stock, Order, OrderItem, Recipe, MedicineAnalog
)


class UserAccountAdminForm(forms.ModelForm):
    password = forms.CharField(
        label="Пароль",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Укажите пароль. При редактировании оставьте поле пустым, чтобы не менять текущий пароль. Пароль будет сохранён в хешированном виде.",
    )

    class Meta:
        model = UserAccount
        fields = ("name", "phone", "email", "role", "password")

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if not self.instance.pk and not password:
            raise forms.ValidationError("Укажите пароль для нового пользователя.")
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        raw_password = self.cleaned_data.get("password")
        if raw_password:
            user.setpass(raw_password)
        if commit:
            user.save()
            self.save_m2m()
        return user


@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    form = UserAccountAdminForm
    list_display = ("name", "phone", "email", "role")
    list_filter = ("role",)
    search_fields = ("name", "phone", "email")
    ordering = ("name",)
    fields = ("name", "phone", "email", "role", "password")


class StockInline(admin.TabularInline):
    model = Stock
    extra = 1


class MedicineAnalogInline(admin.TabularInline):
    model = MedicineAnalog
    fk_name = "medicine"
    extra = 1


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ("name", "active_ingredient", "dosage", "price", "manufacturer", "release_form", "requires_prescription")
    list_filter = ("manufacturer", "release_form", "requires_prescription")
    search_fields = ("name", "active_ingredient", "description")
    inlines = (StockInline, MedicineAnalogInline)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "buyer", "pharmacy", "created_at", "status", "delivery_method")
    list_filter = ("status", "delivery_method", "created_at")
    search_fields = ("number", "buyer__name", "buyer__phone")
    inlines = (OrderItemInline,)


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "buyer", "status", "uploaded_at", "pharmacist")
    list_filter = ("status", "uploaded_at")
    search_fields = ("order__number", "buyer__name")


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("medicine", "pharmacy", "quantity", "updated_at")
    list_filter = ("pharmacy",)
    search_fields = ("medicine__name", "pharmacy__name")


admin.site.register(Manufacturer)
admin.site.register(ReleaseForm)
admin.site.register(Pharmacy)
admin.site.register(MedicineAnalog)
