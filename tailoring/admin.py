from django.contrib import admin

from .models import ResumeTemplate, TailoredResume


@admin.register(ResumeTemplate)
class ResumeTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "pdf_template_name", "is_default")


@admin.register(TailoredResume)
class TailoredResumeAdmin(admin.ModelAdmin):
    list_display = ("posting", "model_used", "created_at")
    readonly_fields = ("created_at",)
