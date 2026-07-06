"""Streamlit page for managing dictionaries."""

from __future__ import annotations

import streamlit as st

from nutag.db.models import (
    Equipment,
    FixedExpenseCategory,
    LaborRate,
)
from nutag.db.runtime import create_app_database
from nutag.services.maintenance import reset_operational_data
from nutag.services.references import (
    create_consumable,
    create_ingredient,
    create_packaging,
    create_preparation_type,
    create_product,
    create_unit,
    delete_consumable,
    delete_ingredient,
    delete_packaging,
    delete_preparation_type,
    delete_product,
    delete_unit,
    list_consumables,
    list_ingredients,
    list_packaging,
    list_preparation_types,
    list_products,
    list_units,
    update_consumable,
    update_ingredient,
    update_packaging,
    update_preparation_type,
    update_product,
    update_unit,
)
from nutag.ui.auth import require_app_access


st.set_page_config(page_title="Справочники | Nutag", page_icon="📖", layout="wide")
require_app_access()

st.title("📖 Справочники")

# Session management
engine, SessionLocal = create_app_database()


def unit_select_options(units):
    """Return labels and lookup for unit selectboxes."""

    labels = [f"{unit.name} ({unit.short_name})" for unit in units]
    return labels, dict(zip(labels, units, strict=True))


def find_by_id(records, record_id: int):
    """Return a record from a freshly loaded list by ID."""

    return next((record for record in records if record.id == record_id), None)


def render_reference_row(label: str, button_key: str, dialog, record_id: int) -> None:
    col_label, col_action = st.columns([6, 1])
    with col_label:
        st.write(label)
    with col_action:
        if st.button("Изменить", key=button_key):
            dialog(record_id)


def handle_dialog_delete(db, *, delete_func, record_id: int, record_name: str, label: str, key_prefix: str) -> None:
    st.divider()
    st.warning(f"Удаление возможно только если {label} не используется в справочниках или операциях.")
    with st.form(f"delete_{key_prefix}_{record_id}"):
        confirm_text = st.text_input("Введите УДАЛИТЬ для подтверждения", key=f"delete_confirm_{key_prefix}_{record_id}")
        delete_submitted = st.form_submit_button("Удалить", type="primary")

        if delete_submitted:
            if confirm_text != "УДАЛИТЬ":
                st.error("Для удаления нужно ввести УДАЛИТЬ")
            else:
                try:
                    delete_func(db, record_id)
                    db.commit()
                    st.success(f"Запись удалена: {record_name}")
                    st.rerun()
                except ValueError as e:
                    db.rollback()
                    st.error(str(e))
                except Exception:
                    db.rollback()
                    st.error("Не удалось удалить запись. Проверьте, что она нигде не используется.")


@st.dialog("Редактировать единицу измерения")
def edit_unit_dialog(unit_id: int) -> None:
    with SessionLocal() as db:
        unit = find_by_id(list_units(db), unit_id)
        if unit is None:
            st.error("Единица измерения не найдена")
            return

        with st.form(f"edit_unit_{unit.id}"):
            edit_name = st.text_input("Название", value=unit.name, key=f"edit_unit_name_{unit.id}")
            edit_short_name = st.text_input("Сокращение", value=unit.short_name, key=f"edit_unit_short_name_{unit.id}")
            edit_comment = st.text_area("Комментарий", value=unit.comment or "", key=f"edit_unit_comment_{unit.id}")
            edit_submitted = st.form_submit_button("Сохранить изменения")

            if edit_submitted:
                try:
                    updated_unit = update_unit(
                        db,
                        unit.id,
                        name=edit_name,
                        short_name=edit_short_name,
                        comment=edit_comment,
                    )
                    db.commit()
                    st.success(f"Единица '{updated_unit.name}' сохранена")
                    st.rerun()
                except ValueError as e:
                    db.rollback()
                    st.error(str(e))
                except Exception:
                    db.rollback()
                    st.error("Не удалось сохранить единицу измерения. Проверьте данные.")

        handle_dialog_delete(
            db,
            delete_func=delete_unit,
            record_id=unit.id,
            record_name=f"Единица '{unit.name}'",
            label="единица",
            key_prefix="unit",
        )


@st.dialog("Редактировать ингредиент")
def edit_ingredient_dialog(ingredient_id: int) -> None:
    with SessionLocal() as db:
        ingredient = find_by_id(list_ingredients(db), ingredient_id)
        units = list_units(db)
        unit_labels, unit_options = unit_select_options(units)
        if ingredient is None:
            st.error("Ингредиент не найден")
            return

        current_label = next(label for label, unit in unit_options.items() if unit.id == ingredient.unit_id)
        with st.form(f"edit_ingredient_{ingredient.id}"):
            edit_name = st.text_input(
                "Название ингредиента",
                value=ingredient.name,
                key=f"edit_ingredient_name_{ingredient.id}",
            )
            edit_unit_name = st.selectbox(
                "Единица измерения",
                options=unit_labels,
                index=unit_labels.index(current_label),
                key=f"edit_ingredient_unit_{ingredient.id}",
            )
            edit_comment = st.text_area(
                "Комментарий",
                value=ingredient.comment or "",
                key=f"edit_ingredient_comment_{ingredient.id}",
            )
            st.caption(
                "Если ингредиент уже использовался в операциях, можно исправить название и комментарий, "
                "но нельзя менять единицу измерения."
            )
            edit_submitted = st.form_submit_button("Сохранить изменения")

            if edit_submitted:
                try:
                    updated_ingredient = update_ingredient(
                        db,
                        ingredient.id,
                        name=edit_name,
                        unit=unit_options[edit_unit_name],
                        comment=edit_comment,
                    )
                    db.commit()
                    st.success(f"Ингредиент '{updated_ingredient.name}' сохранён")
                    st.rerun()
                except ValueError as e:
                    db.rollback()
                    st.error(str(e))
                except Exception:
                    db.rollback()
                    st.error("Не удалось сохранить ингредиент. Проверьте данные.")

        handle_dialog_delete(
            db,
            delete_func=delete_ingredient,
            record_id=ingredient.id,
            record_name=f"Ингредиент '{ingredient.name}'",
            label="ингредиент",
            key_prefix="ingredient",
        )


@st.dialog("Редактировать продукт")
def edit_product_dialog(product_id: int) -> None:
    with SessionLocal() as db:
        product = find_by_id(list_products(db), product_id)
        if product is None:
            st.error("Продукт не найден")
            return

        with st.form(f"edit_product_{product.id}"):
            edit_name = st.text_input(
                "Название продукта",
                value=product.name,
                key=f"edit_product_name_{product.id}",
            )
            edit_comment = st.text_area(
                "Комментарий",
                value=product.comment or "",
                key=f"edit_product_comment_{product.id}",
            )
            edit_submitted = st.form_submit_button("Сохранить изменения")

            if edit_submitted:
                try:
                    updated_product = update_product(db, product.id, name=edit_name, comment=edit_comment)
                    db.commit()
                    st.success(f"Продукт '{updated_product.name}' сохранён")
                    st.rerun()
                except ValueError as e:
                    db.rollback()
                    st.error(str(e))
                except Exception:
                    db.rollback()
                    st.error("Не удалось сохранить продукт. Проверьте данные.")

        handle_dialog_delete(
            db,
            delete_func=delete_product,
            record_id=product.id,
            record_name=f"Продукт '{product.name}'",
            label="продукт",
            key_prefix="product",
        )


@st.dialog("Редактировать вид заготовки")
def edit_preparation_type_dialog(preparation_type_id: int) -> None:
    with SessionLocal() as db:
        preparation_type = find_by_id(list_preparation_types(db), preparation_type_id)
        if preparation_type is None:
            st.error("Вид заготовки не найден")
            return

        with st.form(f"edit_preparation_type_{preparation_type.id}"):
            edit_name = st.text_input(
                "Название вида заготовки",
                value=preparation_type.name,
                key=f"edit_preparation_type_name_{preparation_type.id}",
            )
            edit_comment = st.text_area(
                "Комментарий",
                value=preparation_type.comment or "",
                key=f"edit_preparation_type_comment_{preparation_type.id}",
            )
            edit_submitted = st.form_submit_button("Сохранить изменения")

            if edit_submitted:
                try:
                    updated_preparation_type = update_preparation_type(
                        db,
                        preparation_type.id,
                        name=edit_name,
                        comment=edit_comment,
                    )
                    db.commit()
                    st.success(f"Вид заготовки '{updated_preparation_type.name}' сохранён")
                    st.rerun()
                except ValueError as e:
                    db.rollback()
                    st.error(str(e))
                except Exception:
                    db.rollback()
                    st.error("Не удалось сохранить вид заготовки. Проверьте данные.")

        handle_dialog_delete(
            db,
            delete_func=delete_preparation_type,
            record_id=preparation_type.id,
            record_name=f"Вид заготовки '{preparation_type.name}'",
            label="вид заготовки",
            key_prefix="preparation_type",
        )


@st.dialog("Редактировать упаковку")
def edit_packaging_dialog(packaging_id: int) -> None:
    with SessionLocal() as db:
        packaging_item = find_by_id(list_packaging(db), packaging_id)
        units = list_units(db)
        unit_labels, unit_options = unit_select_options(units)
        if packaging_item is None:
            st.error("Упаковка не найдена")
            return

        current_label = next(label for label, unit in unit_options.items() if unit.id == packaging_item.unit_id)
        with st.form(f"edit_packaging_{packaging_item.id}"):
            edit_name = st.text_input(
                "Название упаковки",
                value=packaging_item.name,
                key=f"edit_packaging_name_{packaging_item.id}",
            )
            edit_unit_name = st.selectbox(
                "Единица измерения",
                options=unit_labels,
                index=unit_labels.index(current_label),
                key=f"edit_packaging_unit_{packaging_item.id}",
            )
            edit_comment = st.text_area(
                "Комментарий",
                value=packaging_item.comment or "",
                key=f"edit_packaging_comment_{packaging_item.id}",
            )
            st.caption(
                "Если упаковка уже использовалась в операциях, можно исправить название и комментарий, "
                "но нельзя менять единицу измерения."
            )
            edit_submitted = st.form_submit_button("Сохранить изменения")

            if edit_submitted:
                try:
                    updated_packaging = update_packaging(
                        db,
                        packaging_item.id,
                        name=edit_name,
                        unit=unit_options[edit_unit_name],
                        comment=edit_comment,
                    )
                    db.commit()
                    st.success(f"Упаковка '{updated_packaging.name}' сохранена")
                    st.rerun()
                except ValueError as e:
                    db.rollback()
                    st.error(str(e))
                except Exception:
                    db.rollback()
                    st.error("Не удалось сохранить упаковку. Проверьте данные.")

        handle_dialog_delete(
            db,
            delete_func=delete_packaging,
            record_id=packaging_item.id,
            record_name=f"Упаковка '{packaging_item.name}'",
            label="упаковка",
            key_prefix="packaging",
        )


@st.dialog("Редактировать расходник")
def edit_consumable_dialog(consumable_id: int) -> None:
    with SessionLocal() as db:
        consumable = find_by_id(list_consumables(db), consumable_id)
        units = list_units(db)
        unit_labels, unit_options = unit_select_options(units)
        if consumable is None:
            st.error("Расходник не найден")
            return

        current_label = next(label for label, unit in unit_options.items() if unit.id == consumable.unit_id)
        with st.form(f"edit_consumable_{consumable.id}"):
            edit_name = st.text_input("Название", value=consumable.name, key=f"edit_consumable_name_{consumable.id}")
            edit_unit_name = st.selectbox(
                "Единица измерения",
                options=unit_labels,
                index=unit_labels.index(current_label),
                key=f"edit_consumable_unit_{consumable.id}",
            )
            edit_comment = st.text_area(
                "Комментарий",
                value=consumable.comment or "",
                key=f"edit_consumable_comment_{consumable.id}",
            )
            st.caption(
                "Если расходник уже использовался в операциях, можно исправить название и комментарий, "
                "но нельзя менять единицу измерения."
            )
            edit_submitted = st.form_submit_button("Сохранить изменения")

            if edit_submitted:
                try:
                    updated_consumable = update_consumable(
                        db,
                        consumable.id,
                        name=edit_name,
                        unit=unit_options[edit_unit_name],
                        comment=edit_comment,
                    )
                    db.commit()
                    st.success(f"Расходник '{updated_consumable.name}' сохранён")
                    st.rerun()
                except ValueError as e:
                    db.rollback()
                    st.error(str(e))
                except Exception:
                    db.rollback()
                    st.error("Не удалось сохранить расходник. Проверьте данные.")

        handle_dialog_delete(
            db,
            delete_func=delete_consumable,
            record_id=consumable.id,
            record_name=f"Расходник '{consumable.name}'",
            label="расходник",
            key_prefix="consumable",
        )


tabs = st.tabs(
    [
        "Единицы измерения",
        "Ингредиенты",
        "Продукты",
        "Виды заготовок",
        "Упаковка",
        "Расходники",
        "Оборудование",
        "Постоянные расходы",
        "Стоимость труда",
        "Обслуживание",
    ]
)

# --- Units Tab ---
with tabs[0]:
    st.header("Единицы измерения")

    with st.form("add_unit"):
        st.subheader("Добавить единицу")
        name = st.text_input("Название")
        short_name = st.text_input("Сокращение")
        comment = st.text_area("Комментарий")
        submitted = st.form_submit_button("Добавить")

        if submitted:
            if not name.strip() or not short_name.strip():
                st.error("Название и сокращение обязательны")
            else:
                with SessionLocal() as db:
                    try:
                        new_unit = create_unit(db, name=name, short_name=short_name, comment=comment)
                        db.commit()
                        st.success(f"Единица '{new_unit.name}' добавлена")
                    except ValueError as e:
                        db.rollback()
                        st.error(str(e))
                    except Exception:
                        db.rollback()
                        st.error(
                            "Не удалось добавить единицу измерения. "
                            "Проверьте, что название и сокращение не дублируются."
                        )

    st.subheader("Список единиц")
    with SessionLocal() as db:
        units = list_units(db)
        if units:
            for unit in units:
                render_reference_row(
                    f"**{unit.name}** ({unit.short_name})",
                    f"open_edit_unit_{unit.id}",
                    edit_unit_dialog,
                    unit.id,
                )
        else:
            st.info("Справочник пуст")

# --- Ingredients Tab ---
with tabs[1]:
    st.header("Ингредиенты")

    ingredient_form_version = st.session_state.setdefault("ingredient_form_version", 0)

    with SessionLocal() as db:
        units = list_units(db)
        unit_labels, unit_options = unit_select_options(units)

        if not unit_options:
            st.warning("Сначала добавьте единицы измерения")
        else:
            with st.form("add_ingredient"):
                st.subheader("Добавить ингредиент")
                name = st.text_input("Название ингредиента", key=f"ingredient_name_{ingredient_form_version}")
                unit_name = st.selectbox(
                    "Единица измерения",
                    options=unit_labels,
                    key=f"ingredient_unit_{ingredient_form_version}",
                )
                comment = st.text_area("Комментарий", key=f"ingredient_comment_{ingredient_form_version}")
                submitted = st.form_submit_button("Добавить")

                if submitted:
                    try:
                        new_ingredient = create_ingredient(
                            db,
                            name=name,
                            unit=unit_options[unit_name],
                            comment=comment,
                        )
                        db.commit()
                        st.session_state["ingredient_form_version"] = ingredient_form_version + 1
                        st.success(f"Ингредиент '{new_ingredient.name}' добавлен")
                        st.rerun()
                    except ValueError as e:
                        db.rollback()
                        st.error(str(e))
                    except Exception:
                        db.rollback()
                        st.error("Не удалось добавить ингредиент. Проверьте данные и повторите попытку.")

    st.subheader("Список ингредиентов")
    with SessionLocal() as db:
        ingredients = list_ingredients(db)
        if ingredients:
            for ingredient in ingredients:
                render_reference_row(
                    f"**{ingredient.name}** ({ingredient.unit.short_name})",
                    f"open_edit_ingredient_{ingredient.id}",
                    edit_ingredient_dialog,
                    ingredient.id,
                )
        else:
            st.info("Справочник пуст")

# --- Products Tab ---
with tabs[2]:
    st.header("Продукты")

    with st.form("add_product"):
        st.subheader("Добавить продукт")
        name = st.text_input("Название продукта")
        comment = st.text_area("Комментарий", key="prod_comment")
        submitted = st.form_submit_button("Добавить")

        if submitted:
            if not name:
                st.error("Название обязательно")
            else:
                with SessionLocal() as db:
                    try:
                        new_product = create_product(db, name=name, comment=comment)
                        db.commit()
                        st.success(f"Продукт '{new_product.name}' добавлен")
                    except ValueError as e:
                        db.rollback()
                        st.error(str(e))
                    except Exception:
                        db.rollback()
                        st.error("Не удалось добавить продукт. Проверьте данные и повторите попытку.")

    st.subheader("Список продуктов")
    with SessionLocal() as db:
        products = list_products(db)
        if products:
            for product in products:
                render_reference_row(
                    f"**{product.name}**",
                    f"open_edit_product_{product.id}",
                    edit_product_dialog,
                    product.id,
                )
        else:
            st.info("Справочник пуст")

# --- Preparation Types Tab ---
with tabs[3]:
    st.header("Виды заготовок")

    with st.form("add_preparation_type"):
        st.subheader("Добавить вид заготовки")
        name = st.text_input("Название вида заготовки")
        comment = st.text_area("Комментарий", key="prep_type_comment")
        submitted = st.form_submit_button("Добавить")

        if submitted:
            if not name:
                st.error("Название обязательно")
            else:
                with SessionLocal() as db:
                    try:
                        new_preparation_type = create_preparation_type(db, name=name, comment=comment)
                        db.commit()
                        st.success(f"Вид заготовки '{new_preparation_type.name}' добавлен")
                    except ValueError as e:
                        db.rollback()
                        st.error(str(e))
                    except Exception:
                        db.rollback()
                        st.error("Не удалось добавить вид заготовки. Проверьте данные и повторите попытку.")

    st.subheader("Список видов заготовок")
    with SessionLocal() as db:
        preparation_types = list_preparation_types(db)
        if preparation_types:
            for preparation_type in preparation_types:
                render_reference_row(
                    f"**{preparation_type.name}**",
                    f"open_edit_preparation_type_{preparation_type.id}",
                    edit_preparation_type_dialog,
                    preparation_type.id,
                )
        else:
            st.info("Справочник пуст")

# --- Packaging Tab ---
with tabs[4]:
    st.header("Упаковка")

    with SessionLocal() as db:
        units = list_units(db)
        unit_labels, unit_options = unit_select_options(units)

        if not unit_options:
            st.warning("Сначала добавьте единицы измерения")
        else:
            with st.form("add_packaging"):
                st.subheader("Добавить упаковку")
                name = st.text_input("Название упаковки")
                unit_name = st.selectbox("Единица измерения", options=unit_labels, key="pkg_unit")
                comment = st.text_area("Комментарий", key="pkg_comment")
                submitted = st.form_submit_button("Добавить")

                if submitted:
                    if not name:
                        st.error("Название обязательно")
                    else:
                        try:
                            new_packaging = create_packaging(
                                db,
                                name=name,
                                unit=unit_options[unit_name],
                                comment=comment,
                            )
                            db.commit()
                            st.success(f"Упаковка '{new_packaging.name}' добавлена")
                        except ValueError as e:
                            db.rollback()
                            st.error(str(e))
                        except Exception:
                            db.rollback()
                            st.error("Не удалось добавить упаковку. Проверьте данные и повторите попытку.")

    st.subheader("Список упаковок")
    with SessionLocal() as db:
        packaging_items = list_packaging(db)
        if packaging_items:
            for packaging_item in packaging_items:
                render_reference_row(
                    f"**{packaging_item.name}** ({packaging_item.unit.short_name})",
                    f"open_edit_packaging_{packaging_item.id}",
                    edit_packaging_dialog,
                    packaging_item.id,
                )
        else:
            st.info("Справочник пуст")

# --- Consumables Tab ---
with tabs[5]:
    st.header("Расходники")

    with SessionLocal() as db:
        units = list_units(db)
        unit_labels, unit_options = unit_select_options(units)

        if not unit_options:
            st.warning("Сначала добавьте единицы измерения")
        else:
            with st.form("add_consumable"):
                st.subheader("Добавить расходник")
                name = st.text_input("Название")
                unit_name = st.selectbox("Единица измерения", options=unit_labels, key="cons_unit")
                comment = st.text_area("Комментарий", key="cons_comment")
                submitted = st.form_submit_button("Добавить")

                if submitted:
                    if not name:
                        st.error("Название обязательно")
                    else:
                        try:
                            new_consumable = create_consumable(
                                db,
                                name=name,
                                unit=unit_options[unit_name],
                                comment=comment,
                            )
                            db.commit()
                            st.success(f"Расходник '{new_consumable.name}' добавлен")
                        except ValueError as e:
                            db.rollback()
                            st.error(str(e))
                        except Exception:
                            db.rollback()
                            st.error("Не удалось добавить расходник. Проверьте данные и повторите попытку.")

    st.subheader("Список расходников")
    with SessionLocal() as db:
        consumables = list_consumables(db)
        if consumables:
            for consumable in consumables:
                render_reference_row(
                    f"**{consumable.name}** ({consumable.unit.short_name})",
                    f"open_edit_consumable_{consumable.id}",
                    edit_consumable_dialog,
                    consumable.id,
                )
        else:
            st.info("Справочник пуст")

# --- Equipment Tab ---
with tabs[6]:
    st.header("Оборудование")

    with st.form("add_equipment"):
        st.subheader("Добавить оборудование")
        name = st.text_input("Название")
        cost = st.number_input("Стоимость покупки", min_value=0.0, step=100.0)
        life = st.number_input("Срок полезного использования (мес)", min_value=1, step=1)
        hourly_cost = st.number_input("Стоимость 1 часа работы", min_value=0.0, step=1.0)
        comment = st.text_area("Комментарий", key="equip_comment")
        submitted = st.form_submit_button("Добавить")

        if submitted:
            if not name:
                st.error("Название обязательно")
            else:
                with SessionLocal() as db:
                    new_equipment = Equipment(
                        name=name,
                        cost=cost,
                        useful_life_months=life,
                        hourly_cost=hourly_cost,
                        comment=comment,
                    )
                    db.add(new_equipment)
                    try:
                        db.commit()
                        st.success(f"Оборудование '{name}' добавлено")
                    except Exception as e:
                        db.rollback()
                        st.error(f"Ошибка при добавлении: {e}")

    st.subheader("Список оборудования")
    with SessionLocal() as db:
        equipment_items = db.query(Equipment).all()
        if equipment_items:
            for equipment_item in equipment_items:
                st.write(
                    f"**{equipment_item.name}** "
                    f"(Стоимость: {equipment_item.cost:,.2f}, Срок: {equipment_item.useful_life_months} мес)"
                )
        else:
            st.info("Справочник пуст")

# --- Fixed Expense Categories Tab ---
with tabs[7]:
    st.header("Категории постоянных расходов")

    with st.form("add_fixed_category"):
        st.subheader("Добавить категорию")
        name = st.text_input("Название")
        comment = st.text_area("Комментарий", key="fixed_cat_comment")
        submitted = st.form_submit_button("Добавить")

        if submitted:
            if not name:
                st.error("Название обязательно")
            else:
                with SessionLocal() as db:
                    new_category = FixedExpenseCategory(name=name, comment=comment)
                    db.add(new_category)
                    try:
                        db.commit()
                        st.success(f"Категория '{name}' добавлена")
                    except Exception as e:
                        db.rollback()
                        st.error(f"Ошибка при добавлении: {e}")

    st.subheader("Список категорий")
    with SessionLocal() as db:
        categories = db.query(FixedExpenseCategory).all()
        if categories:
            for category in categories:
                st.write(f"**{category.name}**")
        else:
            st.info("Справочник пуст")

# --- Labor Rate Tab ---
with tabs[8]:
    st.header("Стоимость труда")

    with SessionLocal() as db:
        current_rate = db.query(LaborRate).filter(LaborRate.is_active.is_(True)).first()

        with st.form("set_labor_rate"):
            st.subheader("Установить стоимость часа")
            rate_value = st.number_input(
                "Стоимость 1 часа работы",
                min_value=0.0,
                value=float(current_rate.hourly_rate) if current_rate else 0.0,
                step=10.0,
            )
            submitted = st.form_submit_button("Сохранить")

            if submitted:
                if current_rate:
                    current_rate.is_active = False

                new_rate = LaborRate(hourly_rate=rate_value, is_active=True)
                db.add(new_rate)
                try:
                    db.commit()
                    st.success(f"Стоимость часа установлена: {rate_value:,.2f}")
                    st.rerun()
                except Exception as e:
                    db.rollback()
                    st.error(f"Ошибка: {e}")

    if current_rate:
        st.metric("Текущая ставка", f"{current_rate.hourly_rate:,.2f} / час")
    else:
        st.warning("Ставка не установлена")

# --- Maintenance Tab ---
with tabs[9]:
    st.header("Обслуживание системы")
    st.warning("Внимание! Действия в этом разделе необратимы.")

    st.subheader("Очистка операционных данных")
    st.write(
        """
        Эта функция удалит все транзакционные данные:
        - Историю закупок и текущие остатки
        - Все записи о заготовках
        - Все производственные партии и фасовку
        - Все заказы клиентов

        Справочники останутся нетронутыми.
        """
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        confirm_text = st.text_input("Введите слово 'УДАЛИТЬ' для подтверждения", key="reset_confirm")

    if st.button("Сбросить все данные", type="primary", disabled=(confirm_text != "УДАЛИТЬ")):
        try:
            with SessionLocal() as db:
                reset_operational_data(db)
                st.success("Все операционные данные успешно удалены.")
                st.balloons()
        except Exception as e:
            st.error(f"Ошибка при очистке данных: {e}")
