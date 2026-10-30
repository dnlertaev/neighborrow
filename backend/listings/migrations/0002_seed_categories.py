from django.db import migrations


def seed_categories(apps, schema_editor):
    Category = apps.get_model('listings', 'Category')
    for name, slug in [('Tools', 'tools'), ('Garden', 'garden'), ('Outdoors', 'outdoors'),
                       ('Electronics', 'electronics'), ('Sports', 'sports'), ('Home & living', 'home-living')]:
        Category.objects.get_or_create(slug=slug, defaults={'name': name})


class Migration(migrations.Migration):
    dependencies = [('listings', '0001_initial')]
    # Preserve categories on rollback: they may already be referenced by real listings.
    operations = [migrations.RunPython(seed_categories, migrations.RunPython.noop)]
