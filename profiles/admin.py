from django.contrib import admin

from .models import Experience, Profile, Project, Skill, SkillCategory


class ExperienceInline(admin.TabularInline):
    model = Experience
    extra = 0


class ProjectInline(admin.TabularInline):
    model = Project
    extra = 0


class SkillCategoryInline(admin.TabularInline):
    model = SkillCategory
    extra = 0


class SkillInline(admin.TabularInline):
    model = Skill
    extra = 0


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    inlines = [SkillCategoryInline, ExperienceInline, ProjectInline]


@admin.register(SkillCategory)
class SkillCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "profile", "order")
    inlines = [SkillInline]
