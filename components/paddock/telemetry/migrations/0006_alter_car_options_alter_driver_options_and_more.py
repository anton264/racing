# Generated by Django 4.2.1 on 2023-05-07 12:33

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("telemetry", "0005_fastlap_data"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="car",
            options={"ordering": ["name"]},
        ),
        migrations.AlterModelOptions(
            name="driver",
            options={"ordering": ["name"]},
        ),
        migrations.AlterModelOptions(
            name="game",
            options={"ordering": ["name"]},
        ),
        migrations.AlterModelOptions(
            name="lap",
            options={"ordering": ["number"]},
        ),
        migrations.AlterModelOptions(
            name="track",
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="fastlap",
            name="lap",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to="telemetry.lap"),
        ),
    ]
