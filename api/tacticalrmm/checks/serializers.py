import validators as _v
import pytz
from rest_framework import serializers

from .models import Check, CheckHistory
from autotasks.models import AutomatedTask
from scripts.serializers import ScriptSerializer, ScriptCheckSerializer


class AssignedTaskField(serializers.ModelSerializer):
    class Meta:
        model = AutomatedTask
        fields = "__all__"


class CheckSerializer(serializers.ModelSerializer):

    readable_desc = serializers.ReadOnlyField()
    script = ScriptSerializer(read_only=True)
    assigned_task = serializers.SerializerMethodField()
    last_run = serializers.ReadOnlyField(source="last_run_as_timezone")
    history_info = serializers.ReadOnlyField()

    ## Change to return only array of tasks after 9/25/2020
    def get_assigned_task(self, obj):
        if obj.assignedtask.exists():
            tasks = obj.assignedtask.all()
            if len(tasks) == 1:
                return AssignedTaskField(tasks[0]).data
            else:
                return AssignedTaskField(tasks, many=True).data

    class Meta:
        model = Check
        fields = "__all__"

    # https://www.django-rest-framework.org/api-guide/serializers/#object-level-validation
    def validate(self, val):
        try:
            check_type = val["check_type"]
        except KeyError:
            return val
        # disk checks
        # make sure no duplicate diskchecks exist for an agent/policy
        if check_type == "diskspace" and not self.instance:  # only on create
            checks = (
                Check.objects.filter(**self.context)
                .filter(check_type="diskspace")
                .exclude(managed_by_policy=True)
            )
            for check in checks:
                if val["disk"] in check.disk:
                    raise serializers.ValidationError(
                        f"A disk check for Drive {val['disk']} already exists!"
                    )

        # ping checks
        if check_type == "ping":
            if (
                not _v.ipv4(val["ip"])
                and not _v.ipv6(val["ip"])
                and not _v.domain(val["ip"])
            ):
                raise serializers.ValidationError(
                    "Please enter a valid IP address or domain name"
                )

        if check_type == "cpuload" and not self.instance:
            if (
                Check.objects.filter(**self.context, check_type="cpuload")
                .exclude(managed_by_policy=True)
                .exists()
            ):
                raise serializers.ValidationError(
                    "A cpuload check for this agent already exists"
                )

        if check_type == "memory" and not self.instance:
            if (
                Check.objects.filter(**self.context, check_type="memory")
                .exclude(managed_by_policy=True)
                .exists()
            ):
                raise serializers.ValidationError(
                    "A memory check for this agent already exists"
                )

        return val


class AssignedTaskCheckRunnerField(serializers.ModelSerializer):
    class Meta:
        model = AutomatedTask
        fields = ["id", "enabled"]


class CheckRunnerGetSerializer(serializers.ModelSerializer):
    # only send data needed for agent to run a check
    assigned_tasks = serializers.SerializerMethodField()
    script = ScriptCheckSerializer(read_only=True)

    def get_assigned_tasks(self, obj):
        if obj.assignedtask.exists():
            tasks = obj.assignedtask.all()
            return AssignedTaskCheckRunnerField(tasks, many=True).data

    class Meta:
        model = Check
        exclude = [
            "policy",
            "managed_by_policy",
            "overriden_by_policy",
            "parent_check",
            "name",
            "more_info",
            "last_run",
            "email_alert",
            "text_alert",
            "fails_b4_alert",
            "fail_count",
            "email_sent",
            "text_sent",
            "outage_history",
            "extra_details",
            "stdout",
            "stderr",
            "retcode",
            "execution_time",
            "svc_display_name",
            "svc_policy_mode",
            "created_by",
            "created_time",
            "modified_by",
            "modified_time",
            "history",
        ]


class CheckResultsSerializer(serializers.ModelSerializer):
    # used when patching results from the windows agent
    # no validation needed

    class Meta:
        model = Check
        fields = "__all__"


class CheckHistorySerializer(serializers.ModelSerializer):
    x = serializers.SerializerMethodField()

    def get_x(self, obj):
        return obj.x.astimezone(pytz.timezone(self.context["timezone"])).isoformat()

    # used for return large amounts of graph data
    class Meta:
        model = CheckHistory
        fields = ("x", "y", "results")
