# Generated by Django 4.2.1 on 2023-05-07 12:49

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("telemetry", "0006_alter_car_options_alter_driver_options_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="fastlap",
            name="lap",
        ),
        migrations.AddField(
            model_name="lap",
            name="fast_lap",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE, related_name="laps", to="telemetry.fastlap"
            ),
        ),
    ]
