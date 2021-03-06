"""
    management utility to process out-of-embargo experiments

    Typical usage is with a nighly cron job
"""

import datetime as dt
import sys
import traceback

from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand

from tardis.tardis_portal.models import Experiment, ParameterName, Schema

from mecat.embargo import EXPIRY_DATE_KEY, NAMESPACE


class Command(BaseCommand):

    help = 'Command to process recently out-of-embargoed experiments.  (run nightly with a cron job)'

    option_list = BaseCommand.option_list + (
        make_option('--list',
                    action='store_true',
                    dest='list',
                    default=False,
                    help="Only list the experiments to be un-embargoed, don't actually un-embargo"),
        )

    def handle(self, *args, **options):
        verbosity = int(options.get('verbosity', 1))
        list_only = options.get('list')
        self._log('starting embargo processing\n')

        exps = self._get_experiments_to_publicise(verbosity)
        for exp in exps:
            if verbosity > 0:
                self._log("%s %s\n" % (exp.id, exp))
            if not list_only:
                try:
                    self._unembargo(exp, verbosity)
                except StandardError:
                    self._log(''.join(traceback.format_exception(*sys.exc_info())))
        self._log('finished embargo processing\n')
                    
    def _unembargo(self, experiment, verbosity):
        if verbosity > 0:
            self._log("Publicising %s (%s)\n" % (experiment, experiment.id))

        experiment.public = True
        experiment.save()

    def _get_experiments_to_publicise(self, verbosity):
        embargo_schema = Schema.objects.get(namespace=NAMESPACE)
        expiry_date = ParameterName.objects.get(schema=embargo_schema, name=EXPIRY_DATE_KEY)

        private_experiments = Experiment.objects.filter(public=False)

        defaulted = private_experiments.exclude(experimentparameterset__schema=embargo_schema)
        custom = private_experiments.filter(experimentparameterset__schema=embargo_schema)

        today = dt.date.today()
        custom_expired = custom.filter(experimentparameterset__experimentparameter__name=expiry_date,
                                        experimentparameterset__experimentparameter__datetime_value__lt=today)

        ended_before = dt.date.today() - dt.timedelta(settings.EMBARGO_DAYS)
        default_expired = defaulted.filter(end_time__lt=ended_before)

        all_expired = custom_expired | default_expired

        return all_expired.distinct()

    def _log(self, message):
        import datetime
        timestamp = datetime.datetime.now().strftime('[%d/%b/%Y %H:%M:%S]')
        self.stdout.write(timestamp + ' ')
        self.stdout.write(message)
