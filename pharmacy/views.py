import uuid
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CheckoutForm, LoginForm, RecipeUploadForm, RegisterForm
from .models import Medicine, MedicineAnalog, Order, OrderItem, Pharmacy, Recipe, Stock, UserAccount


def validate_recipe_file(uploaded_file):
    import os

    allowed_extensions = {".jpg", ".jpeg", ".png", ".pdf"}
    extension = os.path.splitext(uploaded_file.name)[1].lower()
    if extension not in allowed_extensions:
        return "Разрешены файлы JPG, PNG и PDF"
    if uploaded_file.size > 10 * 1024 * 1024:
        return "Размер каждого файла не должен превышать 10 МБ."
    return None


def current_user(request):
    user_id = request.session.get("user_account_id")
    if not user_id:
        return None
    return UserAccount.objects.filter(pk=user_id).first()


def login_required_custom(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not current_user(request):
            messages.info(request, "Для продолжения войдите в аккаунт.")
            return redirect("login")
        return view(request, *args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = current_user(request)
            if not user:
                return redirect("login")
            if user.role not in roles:
                raise Http404
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def cart_data(request):
    cart = request.session.get("cart", {})
    ids = [int(key) for key in cart.keys() if str(key).isdigit()]
    medicines = Medicine.objects.filter(pk__in=ids).select_related("manufacturer", "release_form")
    rows = []
    total = Decimal("0.00")
    for medicine in medicines:
        quantity = max(1, int(cart.get(str(medicine.pk), 1)))
        line_total = medicine.price * quantity
        rows.append({"medicine": medicine, "quantity": quantity, "line_total": line_total})
        total += line_total
    return rows, total


def common_context(request, **extra):
    rows, total = cart_data(request)
    context = {
        "current_user": current_user(request),
        "cart_count": sum(row["quantity"] for row in rows),
        "cart_rows": rows,
        "cart_total": total,
    }
    context.update(extra)
    return context


def home(request):
    popular = Medicine.objects.all().order_by("-order_items__quantity", "name").distinct()[:4]
    if not popular:
        popular = Medicine.objects.all()[:4]
    return render(request, "pharmacy/home.html", common_context(request, popular=popular))


def register_view(request):
    if current_user(request):
        return redirect("profile")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        request.session["user_account_id"] = user.pk
        messages.success(request, "Аккаунт успешно создан.")
        return redirect("home")
    return render(request, "pharmacy/register.html", common_context(request, form=form))


def redirect_after_login(user):
    if user.role == "Фармацевт":
        return redirect("pharmacist_recipes")
    if user.role == "Администратор":
        return redirect("/admin/")
    return redirect("profile")


def login_view(request):
    existing_user = current_user(request)
    if existing_user:
        return redirect_after_login(existing_user)

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = UserAccount.objects.filter(phone=form.cleaned_data["phone"]).first()
        if user and user.checkpass(form.cleaned_data["password"]):
            request.session["user_account_id"] = user.pk
            request.session.set_expiry(
                60 * 60 * 24 * 30 if form.cleaned_data["remember"] else 0
            )
            messages.success(request, "Вы вошли в аккаунт.")
            return redirect_after_login(user)

        form.add_error(None, "Неверный номер телефона или пароль.")

    return render(
        request,
        "pharmacy/login.html",
        common_context(request, form=form)
    )


def logout_view(request):
    request.session.pop("user_account_id", None)
    messages.success(request, "Вы вышли из аккаунта.")
    return redirect("home")


def catalog(request):
    qs = Medicine.objects.select_related("manufacturer", "release_form").prefetch_related("stocks")
    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(name__icontains=query) |
            Q(active_ingredient__icontains=query) |
            Q(description__icontains=query) |
            Q(manufacturer__name__icontains=query)
        )
    form_id = request.GET.get("form")
    manufacturer_id = request.GET.get("manufacturer")
    pharmacy_id = request.GET.get("pharmacy")
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")
    available = request.GET.get("available")
    if form_id and form_id.isdigit():
        qs = qs.filter(release_form_id=form_id)
    if manufacturer_id and manufacturer_id.isdigit():
        qs = qs.filter(manufacturer_id=manufacturer_id)
    if pharmacy_id and pharmacy_id.isdigit():
        qs = qs.filter(stocks__pharmacy_id=pharmacy_id, stocks__quantity__gt=0)
    if min_price:
        try:
            qs = qs.filter(price__gte=Decimal(min_price))
        except Exception:
            pass
    if max_price:
        try:
            qs = qs.filter(price__lte=Decimal(max_price))
        except Exception:
            pass
    if available == "1":
        qs = qs.filter(stocks__quantity__gt=0)
    sort = request.GET.get("sort", "popular")
    if sort == "price_asc":
        qs = qs.order_by("price", "name")
    elif sort == "price_desc":
        qs = qs.order_by( "-price", "name")
    elif sort == "name":
        qs = qs.order_by("name")
    else:
        qs = qs.annotate(sold=Sum("order_items__quantity")).order_by("-sold", "name")
    qs = qs.distinct()
    page_obj = Paginator(qs, 9).get_page(request.GET.get("page"))
    context = common_context(
        request,
        page_obj=page_obj,
        forms=__import__("pharmacy.models", fromlist=["ReleaseForm"]).ReleaseForm.objects.all(),
        manufacturers=__import__("pharmacy.models", fromlist=["Manufacturer"]).Manufacturer.objects.all(),
        pharmacies=Pharmacy.objects.all(),
        filters=request.GET,
        query=query,
    )
    return render(request, "pharmacy/catalog.html", context)


def medicine_detail(request, pk):
    medicine = get_object_or_404(Medicine.objects.select_related("manufacturer", "release_form"), pk=pk)
    analogs = Medicine.objects.filter(analog_links_as_target__medicine=medicine)
    stock_rows = medicine.stocks.select_related("pharmacy").filter(quantity__gt=0)
    return render(request, "pharmacy/detail.html", common_context(
        request, medicine=medicine, analogs=analogs, stock_rows=stock_rows
    ))


def add_to_cart(request, pk):
    if request.method != "POST":
        return redirect("medicine_detail", pk=pk)
    medicine = get_object_or_404(Medicine, pk=pk)
    cart = request.session.get("cart", {})
    key = str(medicine.pk)
    cart[key] = min(int(cart.get(key, 0)) + 1, 99)
    request.session["cart"] = cart
    messages.success(request, "Препарат добавлен в корзину.")
    return redirect(request.POST.get("next") or "cart")


def cart_view(request):
    if request.method == "POST":
        cart = request.session.get("cart", {})
        action = request.POST.get("action")
        medicine_id = request.POST.get("medicine_id")
        if medicine_id and medicine_id in cart:
            if action == "remove":
                cart.pop(medicine_id, None)
            elif action == "update":
                try:
                    cart[medicine_id] = min(99, max(1, int(request.POST.get("quantity", 1))))
                except ValueError:
                    pass
        request.session["cart"] = cart
        return redirect("cart")
    rows, total = cart_data(request)
    return render(request, "pharmacy/cart.html", common_context(request, rows=rows, total=total))


@login_required_custom
def checkout(request):
    rows, total = cart_data(request)

    if not rows:
        messages.info(request, "Корзина пуста.")
        return redirect("catalog")

    requires_prescription = any(
        row["medicine"].requires_prescription for row in rows
    )
    prescription_medicines = [
        row["medicine"] for row in rows
        if row["medicine"].requires_prescription
    ]

    recipe_files = request.FILES.getlist("recipe_files")
    form = CheckoutForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        recipe_errors = []
        if requires_prescription and not recipe_files:
            recipe_errors.append(
                "Для оформления заказа с рецептурными препаратами необходимо загрузить рецепт."
            )

        if requires_prescription:
            for uploaded_file in recipe_files:
                error = validate_recipe_file(uploaded_file)
                if error:
                    recipe_errors.append(f"{uploaded_file.name}: {error}")

        if recipe_errors:
            for error in recipe_errors:
                form.add_error(None, error)
        else:
            selected_pharmacy = form.cleaned_data["pharmacy"]
            stock_error = False
            order = None

            with transaction.atomic():
                locked_stocks = {}

                for row in rows:
                    stock = Stock.objects.select_for_update().filter(
                        medicine=row["medicine"],
                        pharmacy=selected_pharmacy
                    ).first()

                    if stock is None or stock.quantity < row["quantity"]:
                        form.add_error(
                            None,
                            f"Недостаточно товара «{row['medicine'].name}» в выбранной аптеке."
                        )
                        stock_error = True
                        break

                    locked_stocks[row["medicine"].pk] = stock

                if not stock_error:
                    buyer = current_user(request)
                    order = Order.objects.create(
                        number=f"AP-{uuid.uuid4().hex[:8].upper()}",
                        buyer=buyer,
                        pharmacy=selected_pharmacy,
                        status="Оформлен",
                        delivery_method=form.cleaned_data["delivery_method"],
                        delivery_address=form.cleaned_data["delivery_address"] or None,
                    )

                    for row in rows:
                        OrderItem.objects.create(
                            order=order,
                            medicine=row["medicine"],
                            quantity=row["quantity"],
                            price_at_order=row["medicine"].price,
                        )

                        stock = locked_stocks[row["medicine"].pk]
                        stock.quantity -= row["quantity"]
                        stock.updated_at = timezone.now()
                        stock.save(update_fields=["quantity", "updated_at"])

                    if requires_prescription:
                        for uploaded_file in recipe_files:
                            Recipe.objects.create(
                                file=uploaded_file,
                                order=order,
                                buyer=buyer,
                            )

                    request.session["cart"] = {}

            if not stock_error and order is not None:
                messages.success(request, "Заказ оформлен. Загруженные рецепты отправлены фармацевту на проверку.")
                return redirect("order_detail", pk=order.pk)

    return render(
        request,
        "pharmacy/checkout.html",
        common_context(
            request,
            form=form,
            rows=rows,
            total=total,
            requires_prescription=requires_prescription,
            prescription_medicines=prescription_medicines,
        )
    )

@login_required_custom
def profile(request):
    user = current_user(request)
    orders = Order.objects.filter(buyer=user).prefetch_related("items", "recipes")
    return render(request, "pharmacy/profile.html", common_context(request, orders=orders))


@login_required_custom
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "recipes"),
        pk=pk,
        buyer=current_user(request),
    )
    recipes = list(order.recipes.all())
    has_pending_recipes = any(
        recipe.status == "Ожидает проверки" for recipe in recipes
    )
    can_upload_recipe = (
        order.has_prescription_medicines
        and not order.can_be_dispensed
        and not has_pending_recipes
    )
    return render(
        request,
        "pharmacy/order_detail.html",
        common_context(
            request,
            order=order,
            has_pending_recipes=has_pending_recipes,
            can_upload_recipe=can_upload_recipe,
        ),
    )


@login_required_custom
def recipe_upload(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "recipes"),
        pk=order_id,
        buyer=current_user(request),
    )

    if not order.has_prescription_medicines:
        messages.info(request, "Для этого заказа рецепт не требуется.")
        return redirect("order_detail", pk=order.pk)

    existing_recipes = list(order.recipes.all())
    if any(recipe.status == "Ожидает проверки" for recipe in existing_recipes):
        messages.info(request, "Рецепт уже отправлен и ожидает проверки фармацевтом.")
        return redirect("order_detail", pk=order.pk)
    if existing_recipes and all(recipe.status == "Одобрен" for recipe in existing_recipes):
        messages.info(request, "Все загруженные рецепты уже одобрены.")
        return redirect("order_detail", pk=order.pk)

    form = RecipeUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        uploaded_file = form.cleaned_data["file"]
        error = validate_recipe_file(uploaded_file)
        if error:
            form.add_error("file", error)
        else:
            for old_recipe in existing_recipes:
                if old_recipe.status == "Отклонён":
                    if old_recipe.file:
                        old_recipe.file.delete(save=False)
                    old_recipe.delete()

            recipe = form.save(commit=False)
            recipe.order = order
            recipe.buyer = current_user(request)
            recipe.status = "Ожидает проверки"
            recipe.comment = ""
            recipe.pharmacist = None
            recipe.save()
            messages.success(request, "Новый рецепт отправлен фармацевту на проверку.")
            return redirect("order_detail", pk=order.pk)

    return render(
        request,
        "pharmacy/recipe_upload.html",
        common_context(request, form=form, order=order),
    )


@role_required("Фармацевт", "Администратор")
def pharmacist_recipes(request):
    recipes = Recipe.objects.select_related("buyer", "order", "pharmacist").all()
    status = request.GET.get("status")
    if status in dict(Recipe.STATUS_CHOICES):
        recipes = recipes.filter(status=status)
    return render(request, "pharmacy/pharmacist_recipes.html", common_context(request, recipes=recipes, selected_status=status))


@role_required("Фармацевт", "Администратор")
def recipe_review(request, pk):
    recipe = get_object_or_404(Recipe.objects.select_related("buyer", "order"), pk=pk)
    if request.method == "POST":
        status = request.POST.get("status")
        if status not in ("Одобрен", "Отклонён"):
            messages.error(request, "Выберите корректный результат проверки.")
        else:
            recipe.status = status
            recipe.comment = request.POST.get("comment", "").strip()
            recipe.pharmacist = current_user(request)
            recipe.save()
            messages.success(request, "Результат проверки сохранён.")
            return redirect("pharmacist_recipes")
    return render(request, "pharmacy/recipe_review.html", common_context(request, recipe=recipe))
