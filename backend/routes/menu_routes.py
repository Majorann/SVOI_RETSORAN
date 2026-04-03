from flask import redirect, render_template, url_for


def menu_item_route(item_id, load_menu_items):
    return redirect(url_for("menu"))


def menu_route(load_menu_items):
    return render_template("menu.html", items=load_menu_items())
