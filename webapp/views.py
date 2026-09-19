from django.views.generic import TemplateView


class LoginPageView(TemplateView):
    template_name = 'webapp/index.html'


class DashboardPageView(TemplateView):
    template_name = 'webapp/dashboard.html'


class VerifyPageView(TemplateView):
    template_name = 'webapp/verify.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['token'] = kwargs['token']
        return context
