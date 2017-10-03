import os
import shutil
import sys
import json
try:
    from StringIO import StringIO as BytesIO
except:
    from io import BytesIO
import unittest


CWD = os.path.dirname(os.path.abspath(__file__))
MS_WD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Allow import of api.py
if os.path.join(MS_WD, 'utils') not in sys.path:
    sys.path.insert(0, os.path.join(MS_WD, 'utils'))
if os.path.join(MS_WD, 'storage') not in sys.path:
    sys.path.insert(0, os.path.join(MS_WD, 'storage'))
# Use multiscanner in ../
sys.path.insert(0, os.path.dirname(CWD))

import api
from sql_driver import Database
from storage import Storage


TEST_DB_PATH = os.path.join(CWD, 'testing.db')
if os.path.exists(TEST_DB_PATH):
    os.remove(TEST_DB_PATH)
DB_CONF = Database.DEFAULTCONF
DB_CONF['db_name'] = TEST_DB_PATH

TEST_UPLOAD_FOLDER = os.path.join(CWD, 'tmp')
if not os.path.isdir(TEST_UPLOAD_FOLDER):
    print('Creating upload dir')
    os.makedirs(TEST_UPLOAD_FOLDER)
api.api_config['api']['upload_folder'] = TEST_UPLOAD_FOLDER

TEST_REPORT = {
    'MD5': '96b47da202ddba8d7a6b91fecbf89a41',
    'SHA256': '26d11f0ea5cc77a59b6e47deee859440f26d2d14440beb712dbac8550d35ef1f',
    'libmagic': 'a /bin/python script text executable',
    'filename': '/opt/other_file'
}


def post_file(app):
    return app.post(
        '/api/v1/tasks',
        data={'file': (BytesIO(b'my file contents'), 'hello world.txt'), })


class MockMultiscannerCelery(object):
    def delay(file_, original_filename, task_id, report_id):
        pass


class MockStorage(object):
    def get_report(self, report_id):
        return TEST_REPORT

    def delete_report(self, report_id):
        return True


class TestURLCase(unittest.TestCase):
    def setUp(self):
        self.sql_db = Database(config=DB_CONF)
        self.sql_db.init_db()
        self.app = api.app.test_client()
        # Replace the real production DB w/ a testing DB
        api.db = self.sql_db
        if not os.path.isdir(TEST_UPLOAD_FOLDER):
            os.makedirs(TEST_UPLOAD_FOLDER)
        api.multiscanner_celery = MockMultiscannerCelery

    def test_index(self):
        expected_response = {'Message': 'True'}
        resp = self.app.get('/')
        self.assertEqual(resp.status_code, api.HTTP_OK)
        self.assertEqual(json.loads(resp.get_data().decode()), expected_response)

    def test_empty_db(self):
        expected_response = {'Tasks': []}
        resp = self.app.get('/api/v1/tasks')
        self.assertEqual(resp.status_code, api.HTTP_OK)
        self.assertEqual(json.loads(resp.get_data().decode()), expected_response)

    def test_create_first_task(self):
        expected_response = {'Message': {'task_ids': [1]}}
        resp = post_file(self.app)
        self.assertEqual(resp.status_code, api.HTTP_CREATED)
        self.assertEqual(json.loads(resp.get_data().decode()), expected_response)

    def tearDown(self):
        # Clean up Test DB and upload folder
        os.remove(TEST_DB_PATH)
        shutil.rmtree(TEST_UPLOAD_FOLDER)


class TestTaskCreateCase(unittest.TestCase):
    def setUp(self):
        self.sql_db = Database(config=DB_CONF)
        self.sql_db.init_db()
        self.app = api.app.test_client()
        # Replace the real production DB w/ a testing DB
        api.db = self.sql_db
        if not os.path.isdir(TEST_UPLOAD_FOLDER):
            os.makedirs(TEST_UPLOAD_FOLDER)
        api.multiscanner_celery = MockMultiscannerCelery

        # populate the DB w/ a task
        post_file(self.app)

    def test_get_task(self):
        expected_response = {
            'Task': {
                'task_id': 1,
                'task_status': 'Pending',
                'sample_id': '114d70ba7d04c76d8c217c970f99682025c89b1a6ffe91eb9045653b4b954eb9',
                'timestamp': None,
            }
        }
        resp = self.app.get('/api/v1/tasks/1')
        self.assertEqual(resp.status_code, api.HTTP_OK)
        self.assertDictEqual(json.loads(resp.get_data().decode()), expected_response)

    def test_get_nonexistent_task(self):
        expected_response = api.TASK_NOT_FOUND
        resp = self.app.get('/api/v1/tasks/2')
        self.assertEqual(resp.status_code, api.HTTP_NOT_FOUND)
        self.assertDictEqual(json.loads(resp.get_data().decode()), expected_response)

    def test_get_task_list(self):
        expected_response = {'Tasks': [{
            'task_id': 1,
            'task_status': 'Pending',
            'sample_id': '114d70ba7d04c76d8c217c970f99682025c89b1a6ffe91eb9045653b4b954eb9',
            'timestamp': None,
        }]}
        resp = self.app.get('/api/v1/tasks')
        self.assertEqual(resp.status_code, api.HTTP_OK)
        self.assertDictEqual(json.loads(resp.get_data().decode()), expected_response)

    def tearDown(self):
        # Clean up Test DB and upload folder
        os.remove(TEST_DB_PATH)
        shutil.rmtree(TEST_UPLOAD_FOLDER)


class TestTaskUpdateCase(unittest.TestCase):
    def setUp(self):
        self.sql_db = Database(config=DB_CONF)
        self.sql_db.init_db()
        self.app = api.app.test_client()
        # Replace the real production DB w/ a testing DB
        api.db = self.sql_db
        if not os.path.isdir(TEST_UPLOAD_FOLDER):
            os.makedirs(TEST_UPLOAD_FOLDER)

        # populate the DB w/ a task
        post_file(self.app)
        self.sql_db.update_task(
            task_id=1,
            task_status='Complete',
        )

    def test_get_updated_task(self):
        expected_response = {
            'Task': {
                'task_id': 1,
                'task_status': 'Complete',
                'sample_id': '114d70ba7d04c76d8c217c970f99682025c89b1a6ffe91eb9045653b4b954eb9',
                'timestamp': None,
            }
        }
        resp = self.app.get('/api/v1/tasks/1')
        self.assertEqual(resp.status_code, api.HTTP_OK)
        self.assertDictEqual(json.loads(resp.get_data().decode()), expected_response)

    def test_delete_nonexistent_task(self):
        expected_response = api.TASK_NOT_FOUND
        resp = self.app.delete('/api/v1/tasks/2')
        self.assertEqual(resp.status_code, api.HTTP_NOT_FOUND)
        self.assertDictEqual(json.loads(resp.get_data().decode()), expected_response)

    def tearDown(self):
        # Clean up Test DB and upload folder
        os.remove(TEST_DB_PATH)
        shutil.rmtree(TEST_UPLOAD_FOLDER)


class TestTaskDeleteCase(unittest.TestCase):
    def setUp(self):
        self.sql_db = Database(config=DB_CONF)
        self.sql_db.init_db()
        self.app = api.app.test_client()
        # Replace the real production DB w/ a testing DB
        api.db = self.sql_db
        if not os.path.isdir(TEST_UPLOAD_FOLDER):
            os.makedirs(TEST_UPLOAD_FOLDER)

        # populate the DB w/ a task
        post_file(self.app)

    def test_delete_task(self):
        expected_response = {'Message': 'Deleted'}
        resp = self.app.delete('/api/v1/tasks/1')
        self.assertEqual(resp.status_code, api.HTTP_OK)
        self.assertDictEqual(json.loads(resp.get_data().decode()), expected_response)

    def test_delete_nonexistent_task(self):
        expected_response = api.TASK_NOT_FOUND
        resp = self.app.delete('/api/v1/tasks/2')
        self.assertEqual(resp.status_code, api.HTTP_NOT_FOUND)
        self.assertDictEqual(json.loads(resp.get_data().decode()), expected_response)

    def tearDown(self):
        # Clean up Test DB and upload folder
        os.remove(TEST_DB_PATH)
        shutil.rmtree(TEST_UPLOAD_FOLDER)


class TestReportCase(unittest.TestCase):
    def setUp(self):
        self.sql_db = Database(config=DB_CONF)
        self.sql_db.init_db()
        self.app = api.app.test_client()
        # Replace the real production DB w/ a testing DB
        api.db = self.sql_db

    '''
    def test_get_report(self):
        expected_response = {'Report': TEST_REPORT}
        resp = self.app.get('/api/v1/tasks/1/report')
        self.assertEqual(resp.status_code, api.HTTP_OK)
        self.assertDictEqual(json.loads(resp.get_data().decode()), expected_response)
    '''

    def test_get_nonexistent_report(self):
        expected_response = api.TASK_NOT_FOUND
        resp = self.app.get('/api/v1/tasks/42/report')
        self.assertEqual(resp.status_code, api.HTTP_NOT_FOUND)
        self.assertDictEqual(json.loads(resp.get_data().decode()), expected_response)

    def tearDown(self):
        pass
