from django.contrib import admin
from .models import Contact, Customer, CustomerChange, Invoice, Job, JobChange


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'company_id', 'email', 'phone', 'city', 'status')
    list_filter = ('status',)
    search_fields = ('name', 'company_id', 'email', 'phone')


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('job_number', 'title', 'customer', 'status', 'due_date', 'completed_at', 'is_archived', 'price')
    list_filter = ('status', 'is_archived')
    search_fields = ('title', 'customer__name')


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'customer', 'role', 'phone', 'email', 'is_primary')
    list_filter = ('role', 'is_primary')
    search_fields = ('name', 'customer__name', 'phone', 'email')


@admin.register(JobChange)
class JobChangeAdmin(admin.ModelAdmin):
    list_display = ('job', 'action', 'user', 'created_at')
    list_filter = ('action', 'created_at')
    readonly_fields = ('job', 'action', 'user', 'changes', 'reason', 'created_at')


@admin.register(CustomerChange)
class CustomerChangeAdmin(admin.ModelAdmin):
    list_display = ('customer', 'action', 'subject', 'user', 'created_at')
    list_filter = ('action', 'created_at')
    readonly_fields = ('customer', 'action', 'subject', 'user', 'changes', 'created_at')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'job', 'supplier_name', 'issue_date', 'due_date', 'total_amount', 'currency')
    search_fields = ('invoice_number', 'job__job_number', 'job__title', 'supplier_name')
    readonly_fields = ('created_at', 'updated_at')

# Register your models here.
