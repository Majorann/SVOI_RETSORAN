from flask import render_template


def menu_item_route(item_id, load_menu_items):
    item = next((dish for dish in load_menu_items() if dish["id"] == item_id), None)
    if item is None:
        return render_template("placeholder.html", title="Блюдо не найдено"), 404
    return render_template("menu-item.html", item=item)


def menu_route(load_menu_items):
    return render_template("menu.html", items=load_menu_items())
