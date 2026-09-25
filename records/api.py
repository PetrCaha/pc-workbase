from rest_framework import serializers, viewsets
from django.utils.translation import gettext as _
class DemoTextSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        for key in ('title', 'description', 'note', 'city'):
            if data.get(key):
                data[key] = _(data[key])
        return data

from .models import Contact, Customer, Job


class ContactSerializer(serializers.ModelSerializer):
    role_label = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = Contact
        fields = ['id', 'name', 'role', 'role_label', 'phone', 'email', 'is_primary']


class CustomerSerializer(DemoTextSerializer):
    jobs_count = serializers.IntegerField(source='jobs.count', read_only=True)
    open_jobs_count = serializers.SerializerMethodField()
    main_contact = serializers.SerializerMethodField()
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Customer
        fields = ['id', 'name', 'company_id', 'email', 'phone', 'street', 'city', 'postal_code', 'note', 'status', 'status_label', 'main_contact', 'jobs_count', 'open_jobs_count', 'created_at', 'updated_at']

    def get_open_jobs_count(self, obj):
        return obj.jobs.filter(is_archived=False).exclude(status__in=[Job.Status.DONE, Job.Status.CANCELLED]).count()

    def get_main_contact(self, obj):
        contact = obj.main_contact
        return ContactSerializer(contact).data if contact else None


class JobSerializer(DemoTextSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    contact_detail = ContactSerializer(source='effective_contact', read_only=True)
    responsible_name = serializers.SerializerMethodField()
    def get_responsible_name(self, obj):
        return obj.responsible.get_full_name() if obj.responsible else ''
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Job
        fields = ['id', 'responsible_name', 'job_number', 'customer', 'customer_name', 'contact', 'contact_detail', 'title', 'description', 'status', 'status_label', 'due_date', 'completed_at', 'is_archived', 'price', 'created_at', 'updated_at']


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Customer.objects.prefetch_related('jobs', 'contacts').all()
    serializer_class = CustomerSerializer


class JobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Job.objects.select_related('customer', 'contact').prefetch_related('customer__contacts').all()
    serializer_class = JobSerializer


class ContactViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ContactSerializer

    def get_queryset(self):
        queryset = Contact.objects.select_related('customer')
        customer_id = self.request.query_params.get('customer')
        if customer_id and not customer_id.isdigit():
            return queryset.none()
        return queryset.filter(customer_id=customer_id) if customer_id else queryset
