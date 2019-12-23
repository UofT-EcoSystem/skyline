import logging

import torch

from innpv.exceptions import AnalysisError

logger = logging.getLogger(__name__)


class IterationProfiler:
    def __init__(self, iteration, input_provider):
        self._iteration = iteration
        self._input_provider = input_provider
        self._start_event = torch.cuda.Event(enable_timing=True)
        self._end_event = torch.cuda.Event(enable_timing=True)

    @classmethod
    def new_from(cls, model_provider, input_provider, iteration_provider):
        model = model_provider()
        iteration = iteration_provider(model)
        return cls(iteration, input_provider)

    def measure_run_time_ms(self, batch_size, initial_repetitions=None):
        """
        Measures the iteration run time in milliseconds.

        NOTE: This method will raise a RuntimeError if there is not enough GPU
              memory to run the iteration.
        """
        inputs = self._input_provider(batch_size=batch_size)

        # Warm up
        self._iteration(*inputs)
        torch.cuda.synchronize()

        def measure(iterations):
            self._start_event.record()
            for _ in range(iterations):
                self._iteration(*inputs)
            self._end_event.record()
            torch.cuda.synchronize()
            return self._start_event.elapsed_time(self._end_event)

        # When measuring the iteration run time of the model, we want to use as
        # few repetitions as possible. The problem is that we do not know how
        # many repetitions we need ahead of time.
        #
        # So the idea here is to iteratively double the number of repetitions
        # we use until we get a stable measurement (less than 5% difference).
        # If the caller knows how many measurements to use, they can pass it in
        # and we'll start from there. We will stop after reaching 100
        # iterations (or 2 * initial_repetitions), whichever is larger.
        #
        # We will return the smaller number of repetitions. This can be used by
        # future callers as the value of the initial_repetitions argument.
        repetitions = 5 if initial_repetitions is None else initial_repetitions
        max_repetitions = (
            50 if initial_repetitions is None else max(50, initial_repetitions)
        )
        lesser = measure(repetitions) / repetitions
        logger.debug("Iters: %d, Measured: %f", repetitions, lesser)
        while repetitions <= max_repetitions:
            doubled = repetitions * 2
            greater = measure(doubled) / doubled
            logger.debug("Iters: %d, Measured: %f", doubled, greater)

            # Stop when the difference between the measurements is less than 5%
            if (max(lesser, greater) / min(lesser, greater)) < 1.05:
                break

            repetitions = doubled
            lesser = greater

        return min(lesser, greater), repetitions

    def safely_measure_run_time_ms(self, batch_size, initial_repetitions=None):
        try:
            return (
                None,
                self.measure_run_time_ms(batch_size, initial_repetitions),
            )
        except RuntimeError as ex:
            message = str(ex)
            if 'CUDA out of memory' in message:
                return (ex, None)
            else:
                raise

    def measure_throughput(self, batch_size):
        samples = self.sample_run_time_ms_by_batch_size(batch_size)
        logger.debug('Num. samples: %d', len(samples))
        return samples[0][0] / samples[0][1] * 1000

    def sample_run_time_ms_by_batch_size(
            self, start_batch_size, num_samples=3):
        samples = []

        # 1. Make sure we can measure the run time of the "start" batch size
        err, start_result = self.safely_measure_run_time_ms(start_batch_size)
        if err is not None:
            raise AnalysisError(str(err), type(err))
        samples.append((start_batch_size, start_result[0]))

        # 2. Perform sampling. We keep a range of "viable" batch sizes, where
        #    the upper limit is a guess on what will fit in memory. We adjust
        #    these limits as we sample.
        max_batch_size = start_batch_size * 2

        if len(samples) < num_samples:
            samples.extend(self._sample_range(
                start_batch_size,
                max_batch_size,
                num_samples=(num_samples - len(samples)),
                is_increasing=True,
            ))

        if len(samples) < num_samples:
            samples.extend(self._sample_range(
                1,
                start_batch_size,
                num_samples=(num_samples - len(samples)),
                is_increasing=False,
            ))

        return samples

    def _sample_range(
            self, min_size, max_size, num_samples, is_increasing=True):
        # The idea here is to sample the range of possible batch sizes by
        # recursively narrowing down the acceptable ranges of batch sizes.

        samples = []
        stack = [(min_size, max_size)]

        while len(samples) < num_samples and len(stack) > 0:
            lower, upper = stack.pop()
            if lower >= upper:
                continue

            next_size = self._select_batch_size(lower, upper, is_increasing)
            logger.debug("Sampling batch size: %d", next_size)
            err, result = self.safely_measure_run_time_ms(next_size)
            if err is not None:
                if is_increasing:
                    stack.append((lower, next_size - 1))
                else:
                    stack.append((next_size + 1, upper))
                continue

            samples.append((next_size, result[0]))

            # Change the order in which we explore each range
            if is_increasing:
                stack.append((lower, next_size - 1))
                stack.append((next_size + 1, upper))
            else:
                stack.append((next_size + 1, upper))
                stack.append((lower, next_size - 1))

        return samples

    def _select_batch_size(self, lower, upper, is_increasing):
        diff = upper - lower
        base = lower if is_increasing else upper
        mult = 1 if is_increasing else -1

        if diff >= 10:
            return base + mult * 10
        elif diff >= 5:
            return base + mult * 5
        else:
            return base + mult * 1