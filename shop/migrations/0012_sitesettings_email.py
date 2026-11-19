from django.db import migrations, models


def fill_shop_email(apps, schema_editor):
    SiteSettings = apps.get_model('shop', 'SiteSettings')
    SiteSettings.objects.filter(email='').update(email='muzflowers@ya.ru')


class Migration(migrations.Migration):
    dependencies = [('shop', '0011_order_delivery_photo_review_permission_given_and_more')]
    operations = [
        migrations.AlterField(
            model_name='sitesettings',
            name='email',
            field=models.EmailField(blank=True, default='muzflowers@ya.ru', help_text='Показывается на сайте и в письмах клиентам', max_length=254, verbose_name='Почта магазина'),
        ),
        migrations.RunPython(fill_shop_email, migrations.RunPython.noop),
    ]
