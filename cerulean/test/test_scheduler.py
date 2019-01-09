import logging
import time
from typing import Any, Tuple

import pytest
from cerulean import (DirectGnuScheduler, FileSystem, JobDescription,
                      JobStatus, Scheduler, SlurmScheduler, TorqueScheduler)


def test_scheduler(scheduler_and_fs: Tuple[Scheduler, FileSystem],
                   caplog: Any) -> None:
    caplog.set_level(logging.DEBUG)
    sched, fs, _ = scheduler_and_fs

    job_desc = JobDescription()
    job_desc.working_directory = '/home'
    job_desc.command = 'ls'
    job_desc.arguments = ['-l']
    job_desc.stdout_file = '/home/cerulean/test_scheduler.out'
    job_id = sched.submit(job_desc)
    print('Job id: {}'.format(job_id))

    while sched.get_status(job_id) != JobStatus.DONE:
        time.sleep(10.0)

    retval = sched.get_exit_code(job_id)
    assert retval == 0

    try:
        output = (fs / 'home/cerulean/test_scheduler.out').read_text()
    except FileNotFoundError:
        msg = ''
        for path in (fs/'home/cerulean').iterdir():
            msg += '{}\n'.format(path)
        pytest.xfail('Output file not found, to be investigated.'
                     ' Debug output: {}'.format(msg))
    assert 'cerulean' in output

    (fs / 'home/cerulean/test_scheduler.out').unlink()


def test_scheduler_cancel(scheduler_and_fs: Tuple[Scheduler, FileSystem],
                          caplog: Any) -> None:
    caplog.set_level(logging.DEBUG)
    sched, fs, _ = scheduler_and_fs

    job_desc = JobDescription()
    job_desc.working_directory = '/home/cerulean'
    job_desc.command = 'sleep'
    job_desc.arguments = ['15']
    job_id = sched.submit(job_desc)
    print('Job id: {}'.format(job_id))

    while sched.get_status(job_id) != JobStatus.RUNNING:
        time.sleep(1.0)

    sched.cancel(job_id)

    t = 0.0
    while sched.get_status(job_id) != JobStatus.DONE:
        time.sleep(1.0)
        t += 1.0
        assert t < 10.0


def test_scheduler_exit_code(scheduler_and_fs: Tuple[Scheduler, FileSystem],
                             caplog: Any) -> None:
    caplog.set_level(logging.DEBUG)
    sched, fs, _ = scheduler_and_fs

    job_desc = JobDescription()
    job_desc.working_directory = '/home/cerulean'
    job_desc.command = 'exit'
    job_desc.arguments = ['5']
    job_id = sched.submit(job_desc)

    while sched.get_status(job_id) != JobStatus.DONE:
        time.sleep(10.0)

    retval = sched.get_exit_code(job_id)
    assert retval == 5


# test_exit_running
    # get_exit_code of a running job returns None


def test_scheduler_timeout(scheduler_and_fs: Tuple[Scheduler, FileSystem]) -> None:
    sched, fs, _ = scheduler_and_fs

    job_desc = JobDescription()
    job_desc.working_directory = '/home/cerulean'
    job_desc.command = '/usr/local/bin/endless-job.sh'
    job_desc.time_reserved = 2
    job_id = sched.submit(job_desc)

    while sched.get_status(job_id) != JobStatus.RUNNING:
        time.sleep(0.1)

    t = 0.0
    while sched.get_status(job_id) != JobStatus.DONE:
        time.sleep(1.0)
        t += 1.0

    assert t < 100.0
    # assert sched.get_exit_code(job_id) != 0


def test_scheduler_wait(scheduler_and_fs: Tuple[Scheduler, FileSystem], caplog: Any) -> None:
    caplog.set_level(logging.DEBUG)
    sched, fs, _ = scheduler_and_fs

    job_desc = JobDescription()
    job_desc.working_directory = '/home/cerulean'
    job_desc.command = 'ls'
    job_desc.time_reserved = 60
    job_id = sched.submit(job_desc)

    exit_code = sched.wait(job_id, 20.0)
    assert exit_code == 0

    job_desc.command = '/usr/local/bin/endless-job.sh'
    job_id = sched.submit(job_desc)

    exit_code = sched.wait(job_id, 1.0)
    assert exit_code is None


def test_scheduler_no_command(scheduler_and_fs: Tuple[Scheduler, FileSystem]) -> None:
    sched = scheduler_and_fs[0]

    job_desc = JobDescription()
    with pytest.raises(ValueError):
        sched.submit(job_desc)


def test_stderr_redirect(scheduler_and_fs: Tuple[Scheduler, FileSystem],
                         caplog: Any) -> None:
    caplog.set_level(logging.DEBUG)
    sched, fs, _ = scheduler_and_fs

    job_desc = JobDescription()
    job_desc.working_directory = '/home'
    job_desc.command = 'ls'
    job_desc.arguments = ['--non-existing-option']
    job_desc.stderr_file = '/home/cerulean/test_stderr_redirect.out'
    job_id = sched.submit(job_desc)
    print('Job id: {}'.format(job_id))

    while sched.get_status(job_id) != JobStatus.DONE:
        time.sleep(10.0)

    retval = sched.get_exit_code(job_id)
    assert retval == 2

    outfile = fs / 'home/cerulean/test_stderr_redirect.out'
    assert 'unrecognized option' in outfile.read_text()
    outfile.unlink()


def test_queue_name(scheduler_and_fs: Tuple[Scheduler, FileSystem]) -> None:
    sched, fs, _ = scheduler_and_fs

    if isinstance(sched, DirectGnuScheduler):
        # this scheduler ignores queues
        return

    job_desc = JobDescription()
    job_desc.working_directory = '/home/cerulean'
    job_desc.command = 'echo'
    job_desc.arguments = ['$SLURM_JOB_PARTITION', '$PBS_QUEUE']
    job_desc.queue_name = 'batch'
    job_desc.stdout_file = '/home/cerulean/test_queue_name.out'
    job_id = sched.submit(job_desc)
    print('Job id: {}'.format(job_id))

    while sched.get_status(job_id) != JobStatus.DONE:
        time.sleep(10.0)

    retval = sched.get_exit_code(job_id)
    assert retval == 0

    outfile = fs / 'home/cerulean/test_queue_name.out'
    assert 'batch' in outfile.read_text()
    outfile.unlink()


def test_num_nodes(scheduler_and_fs: Tuple[Scheduler, FileSystem]) -> None:
    sched, fs, _ = scheduler_and_fs

    if isinstance(sched, DirectGnuScheduler):
        # this scheduler runs everything on the same node
        # and ignores the num_nodes attribute
        return

    job_desc = JobDescription()
    job_desc.working_directory = '/home/cerulean'
    job_desc.num_nodes = 2

    if isinstance(sched, TorqueScheduler):
        job_desc.command = 'wc'
        job_desc.arguments = ['-l', '$PBS_NODEFILE']
    elif isinstance(sched, SlurmScheduler):
        job_desc.command = 'echo'
        job_desc.arguments = ['$SLURM_JOB_NUM_NODES']

    job_desc.queue_name = 'batch'
    job_desc.stdout_file = '/home/cerulean/test_num_nodes.out'
    job_id = sched.submit(job_desc)

    while sched.get_status(job_id) != JobStatus.DONE:
        time.sleep(10.0)

    outfile = fs / 'home/cerulean/test_num_nodes.out'
    num_nodes_output = outfile.read_text()
    assert '2' in outfile.read_text()
    outfile.unlink()


def test_environment(scheduler_and_fs: Tuple[Scheduler, FileSystem]) -> None:
    sched, fs, _ = scheduler_and_fs

    job_desc = JobDescription()
    job_desc.environment['ENVIRONMENT_TEST1'] = 'test_environment_value1'
    job_desc.environment['ENVIRONMENT_TEST2'] = 'test_environment_value2'
    job_desc.command = 'echo'
    job_desc.arguments = ['$ENVIRONMENT_TEST1', '$ENVIRONMENT_TEST2']
    job_desc.stdout_file = '/home/cerulean/test_environment.out'

    job_id = sched.submit(job_desc)
    print('Job id: {}'.format(job_id))

    while sched.get_status(job_id) != JobStatus.DONE:
        time.sleep(10.0)

    retval = sched.get_exit_code(job_id)
    assert retval == 0

    outfile = fs / 'home/cerulean/test_environment.out'
    assert 'test_environment_value1' in outfile.read_text()
    assert 'test_environment_value2' in outfile.read_text()
    outfile.unlink()


def test_prefix(request: Any, scheduler_and_fs: Tuple[Scheduler, FileSystem]
                ) -> None:
    sched, fs, fixture_id = scheduler_and_fs

    # We have tests running in parallel, so use a unique name
    prefix_file = 'prefixtest_{}.txt'.format(fixture_id)
    prefix_path = fs / 'home' / 'cerulean' / prefix_file
    print(prefix_path)

    setattr(sched, '_{}__prefix'.format(sched.__class__.__name__),
            'echo prefixtest >>{} ;'.format(prefix_path))

    job_desc = JobDescription()
    job_desc.working_directory = '/home'
    job_desc.command = 'ls'
    job_id = sched.submit(job_desc)
    print('Job id: {}'.format(job_id))

    output_lines = len(prefix_path.read_text().splitlines())
    assert output_lines >= 1

    print('getting status')
    while sched.get_status(job_id) != JobStatus.DONE:
        time.sleep(10.0)
        print('getting status')

    output_lines = len(prefix_path.read_text().splitlines()) - output_lines
    assert output_lines >= 1

    print('getting exit code')
    retval = sched.get_exit_code(job_id)
    assert retval == 0
    output_lines = len(prefix_path.read_text().splitlines()) - output_lines
    assert output_lines >= 1

    print('cancelling')
    sched.cancel(job_id)
    output_lines = len(prefix_path.read_text().splitlines()) - output_lines
    assert output_lines >= 1

    prefix_path.unlink()
    setattr(sched, '_{}__prefix'.format(sched.__class__.__name__), '')
