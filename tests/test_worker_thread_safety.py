import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).parents[1]
TREE=ast.parse((ROOT/'rdf.py').read_text(encoding='utf-8'))
APP=next(node for node in TREE.body if isinstance(node,ast.ClassDef) and node.name=='App')

def method(name):
    return next(node for node in APP.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==name)

class WorkerThreadSafetyTests(unittest.TestCase):
    def test_analysis_worker_does_not_call_tkinter_after(self):
        worker=method('analyze')
        calls=[node for node in ast.walk(worker) if isinstance(node,ast.Call)]
        self.assertFalse(any(isinstance(node.func,ast.Attribute) and node.func.attr=='after' for node in calls))

    def test_analysis_worker_passes_captured_output_format(self):
        start=method('start')
        captures_format=any(
            isinstance(node,ast.Assign)
            and any(isinstance(target,ast.Attribute) and target.attr=='analysis_output_format' for target in node.targets)
            and isinstance(node.value,ast.Call)
            and isinstance(node.value.func,ast.Attribute)
            and node.value.func.attr=='get'
            for node in ast.walk(start)
        )
        self.assertTrue(captures_format)

        worker=method('analyze')
        calls=[node for node in ast.walk(worker) if isinstance(node,ast.Call)]
        for name in ('compose_filename','filename_with_selected_extension'):
            matching=[node for node in calls if isinstance(node.func,ast.Attribute) and node.func.attr==name]
            self.assertTrue(matching)
            self.assertTrue(all(node.args[-1].id=='output_format' for node in matching))

    def test_analysis_events_are_applied_by_main_thread_poll(self):
        worker=method('analyze')
        self.assertTrue(any(
            isinstance(node,ast.Call)
            and isinstance(node.func,ast.Attribute)
            and node.func.attr=='put'
            for node in ast.walk(worker)
        ))
        poll=method('process_analysis_events')
        self.assertTrue(any(
            isinstance(node,ast.Call)
            and isinstance(node.func,ast.Attribute)
            and node.func.attr=='after'
            for node in ast.walk(poll)
        ))

if __name__=='__main__':unittest.main()
