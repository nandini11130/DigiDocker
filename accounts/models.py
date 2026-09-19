from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with an RBAC role.

    STUDENT: uploads/collects their own documents.
    ISSUER: staff member of an Issuer (college/university/UIDAI-mock) who issues
            digitally-signed, auto-verified documents on behalf of students.
    """

    class Role(models.TextChoices):
        STUDENT = 'STUDENT', 'Student'
        ISSUER = 'ISSUER', 'Issuer Staff'

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    # Roll/registration number, used by an Issuer to locate a student when issuing a document.
    roll_number = models.CharField(max_length=50, blank=True, null=True, unique=True)
    phone = models.CharField(max_length=15, blank=True)

    @property
    def is_issuer(self):
        return self.role == self.Role.ISSUER

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT
