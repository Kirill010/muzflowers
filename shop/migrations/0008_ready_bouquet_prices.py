from django.db import migrations


def update_ready_bouquet_prices(apps, schema_editor):
    Product = apps.get_model('shop', 'Product')
    ready_bouquets = Product.objects.using(schema_editor.connection.alias).filter(is_ready=True)

    ready_bouquets.filter(category__slug='roses', slug='klassika', name='Классика').update(price=5000)
    ready_bouquets.filter(category__slug='author', slug='bolshoy-avtorskiy', name='Большой авторский').update(price=7000)


class Migration(migrations.Migration):
    dependencies = [('shop', '0007_bouquet_prices')]
    operations = [migrations.RunPython(update_ready_bouquet_prices, migrations.RunPython.noop)]
