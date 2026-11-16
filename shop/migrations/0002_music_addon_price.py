from django.db import migrations


def align_music_addon_price(apps, schema_editor):
    Addon = apps.get_model('shop', 'Addon')
    Addon.objects.filter(is_music=True, price=290).update(price=300)


def restore_old_price(apps, schema_editor):
    Addon = apps.get_model('shop', 'Addon')
    Addon.objects.filter(is_music=True, price=300).update(price=290)


class Migration(migrations.Migration):
    dependencies = [('shop', '0001_initial')]
    operations = [migrations.RunPython(align_music_addon_price, restore_old_price)]
