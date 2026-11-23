from django.db import models
from django.db.models import Q, F
from django.contrib.auth.hashers import make_password, check_password
from django.core.validators import MinValueValidator
from django.utils import timezone


class UserAccount(models.Model):
    ROLE_CHOICES = [
        ("Покупатель", "Покупатель"),
        ("Фармацевт", "Фармацевт"),
        ("Администратор", "Администратор"),
    ]
    name = models.CharField(max_length=100, verbose_name="Имя")
    phone = models.CharField(max_length=20, unique=True, verbose_name="Телефон")
    email = models.EmailField(max_length=100, unique=True, blank=True, null=True, verbose_name="Почта")
    password = models.CharField(max_length=255, verbose_name="Пароль")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="Покупатель", verbose_name="Роль")

    def setpass(self, rawpass):
        self.password = make_password(rawpass)

    def checkpass(self, rawpass):
        if check_password(rawpass, self.password):
            return True
        if self.password and rawpass == self.password:
            self.setpass(rawpass)
            self.save(update_fields=["password"])
            return True
        return False

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.role})"


class Manufacturer(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Название")
    production_info = models.TextField(max_length=1000, null=True, blank=True, verbose_name="Информация о производстве")
    country = models.CharField(max_length=100, null=True, blank=True, verbose_name="Страна")

    class Meta:
        verbose_name = "Производитель"
        verbose_name_plural = "Производители"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ReleaseForm(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название")
    description = models.TextField(max_length=500, null=True, blank=True, verbose_name="Описание")

    class Meta:
        verbose_name = "Форма выпуска"
        verbose_name_plural = "Формы выпуска"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Pharmacy(models.Model):
    name = models.CharField(max_length=150, verbose_name="Название")
    address = models.CharField(max_length=250, verbose_name="Адрес")
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Телефон")
    working_hours = models.CharField(max_length=100, null=True, blank=True, verbose_name="Режим работы")

    class Meta:
        verbose_name = "Аптека"
        verbose_name_plural = "Аптеки"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Medicine(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название")
    active_ingredient = models.CharField(max_length=150, verbose_name="Действующее вещество")
    description = models.TextField(max_length=2000, null=True, blank=True, verbose_name="Описание")
    image = models.ImageField(upload_to="medicines/", null=True, blank=True, verbose_name="Изображение")
    dosage = models.CharField(max_length=50, verbose_name="Дозировка")
    requires_prescription = models.BooleanField(default=False, verbose_name="Требуется рецепт")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name="Стоимость")
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.PROTECT, related_name="medicines", verbose_name="Производитель")
    release_form = models.ForeignKey(ReleaseForm, on_delete=models.PROTECT, related_name="medicines", verbose_name="Форма выпуска")
    pharmacies = models.ManyToManyField(Pharmacy, through="Stock", related_name="medicines", verbose_name="Аптеки")
    orders = models.ManyToManyField("Order", through="OrderItem", related_name="medicines", verbose_name="Заказы")
    analogs = models.ManyToManyField("self", through="MedicineAnalog", through_fields=("medicine", "analog"), symmetrical=False, related_name="analog_for", verbose_name="Аналоги")

    class Meta:
        verbose_name = "Препарат"
        verbose_name_plural = "Препараты"
        ordering = ["name"]
        constraints = [models.CheckConstraint(condition=Q(price__gt=0), name="medicine_price_positive")]

    def __str__(self):
        return f"{self.name} ({self.dosage})"


class Stock(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="stocks", verbose_name="Препарат")
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name="stocks", verbose_name="Аптека")
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    updated_at = models.DateTimeField(default=timezone.now, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Остаток в аптеке"
        verbose_name_plural = "Остатки в аптеках"
        ordering = ["pharmacy", "medicine"]
        constraints = [
            models.UniqueConstraint(fields=["medicine", "pharmacy"], name="unique_medicine_pharmacy"),
            models.CheckConstraint(condition=Q(quantity__gte=0), name="stock_quantity_nonnegative"),
        ]

    def __str__(self):
        return f"{self.medicine} — {self.pharmacy}: {self.quantity}"


class Order(models.Model):
    DELIVERY_CHOICES = [("Самовывоз", "Самовывоз"), ("Доставка", "Доставка")]
    STATUS_CHOICES = [
        ("Оформлен", "Оформлен"),
        ("В обработке", "В обработке"),
        ("Готов к получению", "Готов к получению"),
        ("Выполнен", "Выполнен"),
        ("Отменён", "Отменён"),
    ]
    number = models.CharField(max_length=30, unique=True, verbose_name="Номер заказа")
    buyer = models.ForeignKey(UserAccount, on_delete=models.PROTECT, related_name="orders", verbose_name="Покупатель")
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.PROTECT, related_name="orders", verbose_name="Аптека")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Дата оформления")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="Оформлен", verbose_name="Статус заказа")
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_CHOICES, verbose_name="Способ получения")
    delivery_address = models.CharField(max_length=250, null=True, blank=True, verbose_name="Адрес доставки")

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(delivery_method="Самовывоз") | (
                    Q(delivery_method="Доставка") & Q(delivery_address__isnull=False) & ~Q(delivery_address="")
                ),
                name="delivery_address_required",
            )
        ]

    def __str__(self):
        return self.number

    @property
    def total(self):
        return sum((item.quantity * item.price_at_order for item in self.items.all()), 0)

    @property
    def has_prescription_medicines(self):
        return self.items.filter(
            medicine__requires_prescription=True
        ).exists()


    @property
    def can_be_dispensed(self):
        if not self.has_prescription_medicines:
            return True

        recipes = self.recipes.all()

        return recipes.exists() and not recipes.exclude(
            status="Одобрен"
        ).exists()


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="Заказ")
    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT, related_name="order_items", verbose_name="Препарат")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Количество")
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена на момент заказа")

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"
        ordering = ["order"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="order_item_quantity_positive"),
            models.CheckConstraint(condition=Q(price_at_order__gt=0), name="order_item_price_positive"),
            models.UniqueConstraint(fields=["order", "medicine"], name="unique_medicine_in_order"),
        ]

    def __str__(self):
        return f"{self.medicine} — заказ {self.order.number}"


class Recipe(models.Model):
    STATUS_CHOICES = [
        ("Ожидает проверки", "Ожидает проверки"),
        ("Одобрен", "Одобрен"),
        ("Отклонён", "Отклонён"),
    ]
    file = models.FileField(upload_to="recipes/", verbose_name="Файл рецепта")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="Ожидает проверки", verbose_name="Статус проверки")
    uploaded_at = models.DateTimeField(default=timezone.now, verbose_name="Дата загрузки")
    comment = models.TextField(max_length=500, null=True, blank=True, verbose_name="Комментарий")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="recipes", verbose_name="Заказ")
    buyer = models.ForeignKey(UserAccount, on_delete=models.PROTECT, related_name="uploaded_recipes", verbose_name="Покупатель")
    pharmacist = models.ForeignKey(UserAccount, on_delete=models.PROTECT, related_name="checked_recipes", null=True, blank=True, verbose_name="Фармацевт")

    class Meta:
        verbose_name = "Рецепт"
        verbose_name_plural = "Рецепты"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Рецепт №{self.pk} — {self.status}"


class MedicineAnalog(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="analog_links", verbose_name="Основной препарат")
    analog = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="analog_links_as_target", verbose_name="Препарат-аналог")

    class Meta:
        verbose_name = "Аналог препарата"
        verbose_name_plural = "Аналоги препаратов"
        ordering = ["medicine"]
        constraints = [
            models.UniqueConstraint(fields=["medicine", "analog"], name="unique_medicine_analog"),
            models.CheckConstraint(condition=~Q(medicine=F("analog")), name="medicine_cannot_be_own_analog"),
        ]

    def __str__(self):
        return f"{self.medicine} — аналог: {self.analog}"
