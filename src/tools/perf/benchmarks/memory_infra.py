# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from core import perf_benchmark

from telemetry import benchmark
from telemetry.timeline import chrome_trace_category_filter
from telemetry.timeline import chrome_trace_config
from telemetry.web_perf import timeline_based_measurement

import page_sets


# See tr.v.Numeric.getSummarizedScalarNumericsWithNames()
# https://github.com/catapult-project/catapult/blob/master/tracing/tracing/value/numeric.html#L323
_IGNORED_STATS_RE = re.compile(
    r'(?<!dump)(?<!process)_(std|count|max|min|sum|pct_\d{4}(_\d+)?)$')


class _MemoryInfra(perf_benchmark.PerfBenchmark):
  """Base class for new-generation memory benchmarks based on memory-infra.

  This benchmark records data using memory-infra (https://goo.gl/8tGc6O), which
  is part of chrome tracing, and extracts it using timeline-based measurements.
  """

  def CreateTimelineBasedMeasurementOptions(self):
    # Enable only memory-infra, to get memory dumps, and blink.console, to get
    # the timeline markers used for mapping threads to tabs.
    trace_memory = chrome_trace_category_filter.ChromeTraceCategoryFilter(
        filter_string='-*,blink.console,disabled-by-default-memory-infra')
    tbm_options = timeline_based_measurement.Options(
        overhead_level=trace_memory)
    tbm_options.config.enable_android_graphics_memtrack = True
    tbm_options.SetTimelineBasedMetrics(['memoryMetric'])
    # Setting an empty memory dump config disables periodic dumps.
    tbm_options.config.chrome_trace_config.SetMemoryDumpConfig(
        chrome_trace_config.MemoryDumpConfig())
    return tbm_options


# TODO(bashi): Workaround for http://crbug.com/532075.
# @benchmark.Enabled('android') shouldn't be needed.
@benchmark.Enabled('android')
class MemoryBenchmarkTop10Mobile(_MemoryInfra):
  """Measure foreground/background memory on top 10 mobile page set.

  This metric provides memory measurements for the System Health Plan of
  Chrome on Android.
  """
  page_set = page_sets.MemoryTop10Mobile
  options = {'pageset_repeat': 5}

  @classmethod
  def Name(cls):
    return 'memory.top_10_mobile'

  @classmethod
  def ShouldTearDownStateAfterEachStoryRun(cls):
    return False

  @classmethod
  def ShouldDisable(cls, possible_browser):
    # TODO(crbug.com/586148): Benchmark should not depend on DeskClock app.
    return not possible_browser.platform.CanLaunchApplication(
        'com.google.android.deskclock')

  @classmethod
  def ValueCanBeAddedPredicate(cls, value, is_first_result):
    # TODO(crbug.com/610962): Remove this stopgap when the perf dashboard
    # is able to cope with the data load generated by TBMv2 metrics.
    return not _IGNORED_STATS_RE.search(value.name)


class MemoryBenchmarkTop10MobileStress(MemoryBenchmarkTop10Mobile):
  """Run top 10 mobile page set without closing/restarting the browser.

  This benchmark is intended to stress-test the browser, catching memory leaks
  or possible crashes after interacting with the browser for a period of time.
  """
  page_set = page_sets.MemoryTop10MobileRealistic

  @classmethod
  def Name(cls):
    return 'memory.top_10_mobile_stress'

  @classmethod
  def ShouldTearDownStateAfterEachStorySetRun(cls):
    return False


# Benchmark disabled by default. Force to run with --also-run-disabled-tests.
@benchmark.Disabled('all')
class DualBrowserBenchmark(_MemoryInfra):
  """Measures memory usage while interacting with two different browsers.

  The user story involves going back and forth between doing Google searches
  on a webview-based browser (a stand in for the Search app), and loading
  pages on a select browser.
  """
  page_set = page_sets.DualBrowserStorySet
  options = {'pageset_repeat': 5}

  @classmethod
  def Name(cls):
    return 'memory.dual_browser_test'

  @classmethod
  def ShouldTearDownStateAfterEachStoryRun(cls):
    return False

  @classmethod
  def ValueCanBeAddedPredicate(cls, value, is_first_result):
    # TODO(crbug.com/610962): Remove this stopgap when the perf dashboard
    # is able to cope with the data load generated by TBMv2 metrics.
    return not _IGNORED_STATS_RE.search(value.name)


# Benchmark disabled by default. Force to run with --also-run-disabled-tests.
@benchmark.Disabled('all')
class LongRunningDualBrowserBenchmark(_MemoryInfra):
  """Measures memory during prolonged usage of alternating browsers.

  Same as memory.dual_browser_test, but the test is run for 60 iterations
  and the browser is *not* restarted between page set repeats.
  """
  page_set = page_sets.DualBrowserStorySet
  options = {'pageset_repeat': 60}

  @classmethod
  def Name(cls):
    return 'memory.long_running_dual_browser_test'

  @classmethod
  def ShouldTearDownStateAfterEachStoryRun(cls):
    return False

  @classmethod
  def ShouldTearDownStateAfterEachStorySetRun(cls):
    return False

  @classmethod
  def ValueCanBeAddedPredicate(cls, value, is_first_result):
    # TODO(crbug.com/610962): Remove this stopgap when the perf dashboard
    # is able to cope with the data load generated by TBMv2 metrics.
    return not _IGNORED_STATS_RE.search(value.name)


# TODO(bashi): Workaround for http://crbug.com/532075
# @benchmark.Enabled('android') shouldn't be needed.
@benchmark.Enabled('android')
class RendererMemoryBlinkMemoryMobile(_MemoryInfra):
  """Timeline based benchmark for measuring memory consumption on mobile
  sites on which blink's memory consumption is relatively high.
  """
  page_set = page_sets.BlinkMemoryMobilePageSet

  def SetExtraBrowserOptions(self, options):
    super(RendererMemoryBlinkMemoryMobile, self).SetExtraBrowserOptions(
        options)
    options.AppendExtraBrowserArgs([
        # Ignore certs errors because record_wpr cannot handle certs correctly
        # in some cases (e.g. WordPress).
        '--ignore-certificate-errors',
    ])

  @classmethod
  def Name(cls):
    return 'memory.blink_memory_mobile'

  @classmethod
  def ValueCanBeAddedPredicate(cls, value, is_first_result):
    return (not _IGNORED_STATS_RE.search(value.name) and
            'renderer_processes' in value.name)

  @classmethod
  def ShouldDisable(cls, possible_browser):
    # http://crbug.com/634319
    return (possible_browser.browser_type == 'reference' and
            possible_browser.platform.GetDeviceTypeName() == 'Nexus 5X')


class _MemoryV8Benchmark(_MemoryInfra):

  # Report only V8-specific and overall renderer memory values. Note that
  # detailed values reported by the OS (such as native heap) are excluded.
  _V8_AND_OVERALL_MEMORY_RE = re.compile(
      r'renderer_processes:'
      r'(reported_by_chrome:v8|reported_by_os:system_memory:[^:]+$)')

  def CreateTimelineBasedMeasurementOptions(self):
    v8_categories = [
        'blink.console', 'renderer.scheduler', 'v8', 'webkit.console']
    memory_categories = ['blink.console', 'disabled-by-default-memory-infra']
    category_filter = chrome_trace_category_filter.ChromeTraceCategoryFilter(
        ','.join(['-*'] + v8_categories + memory_categories))
    options = timeline_based_measurement.Options(category_filter)
    options.SetTimelineBasedMetrics(['v8AndMemoryMetrics'])
    # Setting an empty memory dump config disables periodic dumps.
    options.config.chrome_trace_config.SetMemoryDumpConfig(
        chrome_trace_config.MemoryDumpConfig())
    return options

  @classmethod
  def ValueCanBeAddedPredicate(cls, value, _):
    if 'memory:chrome' in value.name:
      # TODO(petrcermak): Remove the first two cases once
      # https://codereview.chromium.org/2018503002/ lands in Catapult and rolls
      # into Chromium.
      return ('renderer:subsystem:v8' in value.name or
              'renderer:vmstats:overall' in value.name or
              bool(cls._V8_AND_OVERALL_MEMORY_RE.search(value.name)))
    return 'v8' in value.name


class MemoryLongRunningIdleGmail(_MemoryV8Benchmark):
  """Use (recorded) real world web sites and measure memory consumption
  of long running idle Gmail page """
  page_set = page_sets.LongRunningIdleGmailPageSet

  @classmethod
  def Name(cls):
    return 'memory.long_running_idle_gmail_tbmv2'

  @classmethod
  def ShouldDisable(cls, possible_browser):
    return cls.IsSvelte(possible_browser)  # http://crbug.com/611167


@benchmark.Enabled('has tabs')  # http://crbug.com/612210
class MemoryLongRunningIdleGmailBackground(_MemoryV8Benchmark):
  """Use (recorded) real world web sites and measure memory consumption
  of long running idle Gmail page """
  page_set = page_sets.LongRunningIdleGmailBackgroundPageSet

  @classmethod
  def Name(cls):
    return 'memory.long_running_idle_gmail_background_tbmv2'

  @classmethod
  def ShouldDisable(cls, possible_browser):  # http://crbug.com/616530
    return cls.IsSvelte(possible_browser)
