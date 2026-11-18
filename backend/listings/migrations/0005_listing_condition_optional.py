from django.db import migrations, models


class Migration(migrations.Migration):
    # Schema-only change: existing listings keep their stored type and condition.

    dependencies = [
        ('listings', '0004_listing_archived_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='listing',
            name='condition',
            field=models.CharField(blank=True, choices=[('good', 'Good'), ('like_new', 'Like new'), ('any_working', 'Any working')], default='', max_length=16),
        ),
    ]
