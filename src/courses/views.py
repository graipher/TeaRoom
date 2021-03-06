from django.shortcuts import render
from django.contrib import messages
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import ProcessFormView
from django.views.generic.base import TemplateResponseMixin, ContextMixin, TemplateView, View
from braces.views import LoginRequiredMixin, CsrfExemptMixin, StaffuserRequiredMixin
from django.core.urlresolvers import reverse_lazy
from django.http import HttpResponseRedirect
from django.conf import settings
# Create your views here.
from accounts.models import User
from courses.models import Assigned, Exercise
from .models import *
from django.http import HttpResponse, HttpResponseNotFound
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
import json
import traceback
from datetime import datetime
from itertools import cycle

class CourseListStaffView(LoginRequiredMixin, StaffuserRequiredMixin, ListView):
    model = Course
    template_name = "course_list_staff.html"
    context_object_name = 'courses'
    show_closed = True

    def get_queryset(self):
        print self.show_closed
        self.show_closed = self.request.GET.get('show_closed') != 'False'
        
        if not self.show_closed:
            dataSet = self.model.objects.filter_ongoing()
        else:
            dataSet = self.model.objects.all()
        
        return dataSet

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(CourseListStaffView, self).get_context_data(**kwargs)
        context['show_closed'] = self.show_closed
        return context


class CourseListView(LoginRequiredMixin, ListView):
    messages = {
        'invalid_enroll_id': 'Unable to find the course you want to enroll to. Please contact admins',
        'course_closed': 'Enrollments for this course are closed at this time.'
    }
    model = Course
    context_object_name = 'courses'
    template_name = "course_list.html"
    success_url = reverse_lazy('courses:course-list')

    show_other = False
    show_closed = True

    # custom queryset called by the listview, if getEnroll = False avoid to get enroll_id from request (used by post request).
    # Dont change the default due to the listview compatibility
    def get_queryset(self):
        print self.show_closed
        self.show_other = self.request.GET.get('show_other') == 'True'
        self.show_closed = self.request.GET.get('show_closed') != 'False'
        
        if not self.show_closed:
            dataSet = self.model.objects.filter_ongoing()
        else:
            dataSet = self.model.objects.all()
        if not self.show_other:
            dataSet = dataSet.filter(Students=self.request.user)
        else:
            dataSet = dataSet.exclude(Students=self.request.user)
        return dataSet

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(CourseListView, self).get_context_data(**kwargs)

        context['mycourses'] = self._get_mycourses(context['object_list'])
        context['show_other'] = self.show_other
        context['show_closed'] = self.show_closed
        return context

    def post(self, request):
        # enroll_id corresponds to the course id
        enroll_id = self.request.POST.get('enroll_id') or False
        enroll_id = self._clean_enroll_id(enroll_id)
        if not enroll_id:
            redirect_url = self.request.get_full_path()
            return HttpResponseRedirect(redirect_url)
        else:
            course = self.model.objects.get(id=enroll_id)
            course.enroll(self.request.user.id)
            return HttpResponseRedirect(self.success_url)

    def _clean_enroll_id(self, enroll_id):
        """
        Verify that a course with this ID exists and is open for enrollments
        """
        try:
            enroll_id = int(enroll_id)
            course = self.model.objects.get(id=enroll_id)
        except:
            course = False
        if not course:
            messages.error(self.request, self.messages['invalid_enroll_id'])
            return False
        if not course.Is_enrollment_open():
            messages.error(self.request, self.messages['course_closed'])
            return False
        return enroll_id

    # list of courses to which the user is enrolled
    def _get_mycourses(self, courses_list):
        mycourses = []
        for course in courses_list.filter(Students=self.request.user):
            mycourses.append(course.id)
        return mycourses


class AssignmentListStaffView(LoginRequiredMixin, StaffuserRequiredMixin, ListView):
    
    template_name = "assignment_list_staff.html"
    context_object_name = 'courses'

    def get_queryset(self):
        courses_list = Course.objects.all()
        return courses_list

    def get_context_data(self, **kwargs):
        context = super(AssignmentListStaffView, self).get_context_data(**kwargs)
        courses_list = context['courses']
        if courses_list:
            selected_course_id = self.request.GET.get('selected_course_id') or False
            if selected_course_id:
                try:
                    selected_course = courses_list.get(id=selected_course_id)
                except:
                    selected_course = courses_list[0]
            else:
                selected_course = courses_list[0]
            assignment_list = Assignment.objects.filter(Course=selected_course)

            context['assignments'] = assignment_list
            context['selected_course'] = selected_course

        return context

    def _get_students(self, exercise_set):
        exercise_list = []
        for exercise in exercise_set:
            student_list = []
            for student in exercise.Students.all():
                result_queryset = student.result_set.filter(Exercise=exercise)
                result = result_queryset.last_result()
                if result:
                    student_list.append({"result_id": result.id, "student_id": str(student.id), "student": student.name, "result": str(result.Pass), "date": str(result.Creation_date.strftime('%B %d, %H:%M'))})
                else:
                    student_list.append({"result_id": 'false', "student_id": str(student.id), "student": student.name, "result": 'N/A', "date": 'N/A'})
            exercise_list.append({"exercise_id": str(exercise.id), "student_list": student_list})
        return exercise_list

    def _add_students(self, user, exercise_id, students_id):
        e = Exercise.objects.get(id=exercise_id)
        for student_id in students_id:
            student = User.objects.get(id=student_id)
            if student not in e.Students.all():
                a = Assigned(Student=student, Exercise=e, Assigned_by=user)
                a.save()
        return self._get_students([e])

    def _remove_student(self, exercise_id, student_id):
        e = Exercise.objects.get(id=exercise_id)
        s = User.objects.get(id=student_id)
        Assigned.objects.filter(Student=s, Exercise_id=e).delete()
        return self._get_students([e])

    def _change_date(self, assignment_id, first_date, second_date, use_penalty, penalty_percent):
        print '_change_date: %s %s %s %s' %(first_date, second_date, use_penalty, penalty_percent)
        first_date = datetime.strptime(first_date[:-6], '%Y-%m-%dT%H:%M:%S')
        if second_date:
            second_date = datetime.strptime(second_date[:-6], '%Y-%m-%dT%H:%M:%S')
        use_penalty = use_penalty == 'true'
        penalty_percent = int(penalty_percent)
        a = Assignment.objects.get(id=assignment_id)
        if use_penalty:
            if not second_date or (second_date < first_date): raise Exception('first date after second date.')
            a.Hard_date = second_date
            a.Due_date = first_date
            a.Penalty_percent = penalty_percent
            a.save()
        else:
            print 'Second case'
            a.Hard_date = first_date
            a.Penalty_percent = 0
            a.Due_date = first_date
            a.save()
        print 'worked'
        return {'hard_date': str(a.Hard_date.strftime('%B %d, %H:%M')), 'due_date': str(a.Due_date.strftime('%B %d, %H:%M')), 'penalty_percent': str(a.Penalty_percent), 'use_penalty': str(a.has_due_date())}

    def _change_activation(self, assignment_id, activation_date):
        activation_date = datetime.strptime(activation_date[:-6], '%Y-%m-%dT%H:%M:%S')
        a = Assignment.objects.get(id=assignment_id)
        a.Activation_date = activation_date
        a.save()
        return {'activation_date': str(a.Activation_date.strftime('%B %d, %Y')), 'is_active': str(a.is_active())}

    def _autoshuffle(self, assignment_id, user):
        a = Assignment.objects.get(id=assignment_id)
        grouplist = a.exercise_set.values('Group').distinct()
        for group in grouplist:
            es = a.exercise_set.filter(Group=group['Group']).order_by('?')
            Assigned.objects.filter(Exercise__in=es).delete()
            exercise_set = cycle(es)
            student_set = a.Course.Students.all().order_by('?')
            for student in student_set:
                ad = Assigned(Student=student, Exercise=exercise_set.next(), Assigned_by=user)
                ad.save()
        return self._get_students(es)

    def post(self, request):
        response_data = {}
        user = self.request.user
        action = self.request.POST.get('action') or False
        try:
            if action == 'change-date':
                assignment_id = self.request.POST.get('assignment_id') or False
                first_date = self.request.POST.get('first_date') or False
                if first_date == 'false': second_date = False
                second_date = self.request.POST.get('second_date') or False
                if second_date == 'false': second_date = False
                use_penalty = self.request.POST.get('use_penalty') or False
                penalty_percent = self.request.POST.get('penalty_percent') or False
                updated_assignment = self._change_date(assignment_id, first_date, second_date, use_penalty, penalty_percent)
                response_data['updated_assignment'] = updated_assignment
                response_data['result'] = 'Data change successfull!'
            elif action == 'autoshuffle':
                assignment_id = self.request.POST.get('assignment_id') or False
                if assignment_id:
                    exercise_list = self._autoshuffle(assignment_id, user)
                    response_data['exercise_list'] = exercise_list
                    response_data['result'] = 'Data change successfull!'
            elif action == 'change-activation':
                assignment_id = self.request.POST.get('assignment_id') or False
                activation_date = self.request.POST.get('activation_date') or False
                if assignment_id and activation_date:
                    updated_activation = self._change_activation(assignment_id, activation_date)
                    response_data['updated_activation'] = updated_activation
                    response_data['result'] = 'Data change successfull!'
            elif action == 'add':
                exercise_id = self.request.POST.get('ex_id') or False
                students_id = self.request.POST.get('students_id') or False
                if exercise_id and students_id:
                    exercise_id = int(exercise_id)
                    students_id = map(int, json.loads(students_id))
                    exercise_list = self._add_students(user, exercise_id, students_id)
                    response_data['exercise_list'] = exercise_list
                    response_data['result'] = 'Student adding successfull!'
            elif action == 'remove':
                exercise_id = self.request.POST.get('ex_id') or False
                student_id = self.request.POST.get('student_id') or False
                if exercise_id and student_id:
                    exercise_id = int(exercise_id)
                    students_id = int(student_id)
                    exercise_list = self._remove_student(exercise_id, student_id)
                    response_data['exercise_list'] = exercise_list
                    response_data['result'] = 'Student removing successfull!'
            else:
                raise Exception('Bad action')
        except Exception, e:
            print e, traceback.format_exc()
            response_data['error'] = str(traceback.format_exc())
            
        print json.dumps(response_data)
        return HttpResponse(json.dumps(response_data), content_type="application/json")
    
    
class AssignmentListView(LoginRequiredMixin, ListView):
    
    template_name = "assignment_list.html"
    context_object_name = 'courses'

    def get_queryset(self):
        courses_list = Course.objects.filter(Students=self.request.user)
        return courses_list

    def _get_result_list(self, ex_list):
        result_list = []
        for e in ex_list:
            res_set = e.result_set.filter(Pass=True, User=self.request.user).order_by('-Creation_date')
            if not res_set:
                res_set = e.result_set.filter(Pass=False, User=self.request.user).order_by('-Creation_date')
            if res_set:
                result_list.append(res_set[0])
        return result_list

    def get_context_data(self, **kwargs):
        context = super(AssignmentListView, self).get_context_data(**kwargs)
        courses_list = context['courses']
        if courses_list:
            selected_course_id = self.request.GET.get('selected_course_id') or False
            if selected_course_id:
                try:
                    selected_course = courses_list.get(id=selected_course_id)
                except:
                    selected_course = courses_list[0]
            else:
                selected_course = courses_list[0]
            well_formed_assignment_list = [a.id for a in Assignment.objects.all() if a.is_wellformed()]
            assignment_list = Assignment.objects.filter(Course=selected_course, Activation_date__lte=datetime.now(), id__in=well_formed_assignment_list)
            exercise_list = self.request.user.exercise_set.all()
            result_list = self._get_result_list(exercise_list)
            context['assignments'] = assignment_list
            context['exercises'] = exercise_list
            context['results'] = result_list
            context['selected_course'] = selected_course

        return context


class DownloadUserFileView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        try:
            ex_id = request.GET.get('ex_id') or False
            e = Exercise.objects.get(id=ex_id)

            #filename = 'ex_package.tar.gz'
            #filepath = join(settings.USER_DATA_ROOT, str(e.Folder_path), filename)
            package = UserFile.objects.get(Exercise=e, Type='package')
            filename = package.Name
            filepath = join(settings.USER_DATA_ROOT, package.Folder_path, filename)

            # You got the zip! Now, return it!
            response = HttpResponse(open(filepath, 'rb'), content_type='application/x-gtar')
            response['Content-Disposition'] = 'attachment; filename=%s' % filename
            return response
        except:
            # return HttpResponseNotFound(filepath)
            return HttpResponseNotFound('Exercise package not found. Please contact the admins.')


class ResultListStaffView(LoginRequiredMixin, StaffuserRequiredMixin, ListView):
    model = Course
    template_name = "result_list_staff.html"
    context_object_name = 'courses'
    
    def get_queryset(self):
        courses_list = Course.objects.all()
        return courses_list

    def get_context_data(self, **kwargs):
        context = super(ResultListStaffView, self).get_context_data(**kwargs)
        courses_list = context['courses']
        if courses_list:
            selected_course_id = self.request.GET.get('selected_course_id') or False
            if selected_course_id:
                try:
                    selected_course = courses_list.get(id=selected_course_id)
                except:
                    selected_course = courses_list[0]
            else:
                selected_course = courses_list[0]

            context['exercise_list'] = Exercise.objects.filter(Assignment__Course=selected_course)
            context['selected_course'] = selected_course

        return context


class ResultListView(LoginRequiredMixin, ListView):
    template_name = "result_list.html"
    context_object_name = 'results'

    def get_queryset(self):
        courses_list = Result.objects.order_by('-Creation_date').filter(User=self.request.user)
        return courses_list


def last_result(result_queryset):
    r = result_queryset.filter(Pass=True).order_by('-Creation_date')
    if not r:
        r = result_queryset.filter(Pass=False).order_by('-Creation_date')
    if r:
        return r[0]
    else:
        return False


class SingleResultView(LoginRequiredMixin, TemplateView):
    template_name = "single_result.html"

    def get_context_data(self, **kwargs):
        context = super(SingleResultView, self).get_context_data(**kwargs)

        result_id = self.request.GET.get('result_id') or False
        if result_id:
            res = Result.objects.get(id=result_id)
            context['result_history'] = Result.objects.filter(Exercise=res.Exercise, User=res.User).exclude(id=result_id).order_by('-Creation_date')
            context['result'] = res
        else:
            context['result'] = False
        return context
        
