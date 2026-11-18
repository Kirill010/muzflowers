from django.db import migrations


def update_seeded_prices(apps, schema_editor):
    Product = apps.get_model('shop', 'Product')
    products = Product.objects.using(schema_editor.connection.alias)
    changes = [
        ('roses', 'Мини', 'rose', 990, 3000),
        ('roses', 'Классика', 'rose', 1990, 3000),
        ('mono', 'Хризантемы', 'chrysanthemum', 2190, 3000),
        ('mono', 'Альстромерии', 'alstroemeria', 1690, 3000),
        ('mono', 'Облако гортензий', 'hydrangea', 1890, 3000),
        ('author', 'Премиум', 'mixed', 5990, 15000),
    ]
    for category, name, kind, original, price in changes:
        products.filter(category__slug=category, name=name, art_kind=kind, price=original).update(price=price)


class Migration(migrations.Migration):
    dependencies = [('shop', '0006_vykhino_contacts')]
    operations = [migrations.RunPython(update_seeded_prices, migrations.RunPython.noop)]
