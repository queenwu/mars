#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 1999-2018 Alibaba Group Holding Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest

import numpy as np

import mars.tensor as mt
from mars.session import new_session, Session


class Test(unittest.TestCase):
    def testSessionExecute(self):
        a = mt.random.rand(10, 20)
        res = a.sum().execute()
        self.assertTrue(np.isscalar(res))
        self.assertLess(res, 200)

    def testMultipleOutputExecute(self):
        data = np.random.random((5, 9))

        # test multiple outputs
        arr1 = mt.tensor(data.copy(), chunk_size=3)
        result = mt.modf(arr1).execute()
        expected = np.modf(data)

        np.testing.assert_array_equal(result[0], expected[0])
        np.testing.assert_array_equal(result[1], expected[1])

        # test 1 output
        arr2 = mt.tensor(data.copy(), chunk_size=3)
        result = ((arr2 + 1) * 2).execute()
        expected = (data + 1) * 2

        np.testing.assert_array_equal(result, expected)

        # test multiple outputs, but only execute 1
        arr3 = mt.tensor(data.copy(), chunk_size=3)
        arrs = mt.split(arr3, 3, axis=1)
        result = arrs[0].execute()
        expected = np.split(data, 3, axis=1)[0]

        np.testing.assert_array_equal(result, expected)

        # test multiple outputs, but only execute 1
        data = np.random.randint(0, 10, (5, 5))
        arr3 = mt.tensor(data)
        arrs = mt.linalg.qr(arr3)
        result = arrs[0].execute()
        expected = np.linalg.qr(data)[0]

        np.testing.assert_array_almost_equal(result, expected)

    def testReExecuteSame(self):
        data = np.random.random((5, 9))

        # test run the same tensor
        arr4 = mt.tensor(data.copy(), chunk_size=3) + 1
        result1 = arr4.execute()
        expected = data + 1

        np.testing.assert_array_equal(result1, expected)

        result2 = arr4.execute()

        np.testing.assert_array_equal(result1, result2)

        # test run the same tensor with single chunk
        arr4 = mt.tensor(data.copy())
        result1 = arr4.execute()
        expected = data

        np.testing.assert_array_equal(result1, expected)

        result2 = arr4.execute()
        np.testing.assert_array_equal(result1, result2)

        # modify result
        sess = Session.default_or_local()
        executor = sess._sess._executor
        executor.chunk_result[arr4.chunks[0].key] = data + 2

        result3 = arr4.execute()
        np.testing.assert_array_equal(result3, data + 2)

        # test run same key tensor
        arr5 = mt.ones((10, 10), chunk_size=3)
        result1 = arr5.execute()

        del arr5
        arr6 = mt.ones((10, 10), chunk_size=3)
        result2 = arr6.execute()

        np.testing.assert_array_equal(result1, result2)

    def testExecuteBothExecutedAndNot(self):
        data = np.random.random((5, 9))

        arr1 = mt.tensor(data, chunk_size=4) * 2
        arr2 = mt.tensor(data) + 1

        np.testing.assert_array_equal(arr2.execute(), data + 1)

        # modify result
        sess = Session.default_or_local()
        executor = sess._sess._executor
        executor.chunk_result[arr2.chunks[0].key] = data + 2

        results = sess.run(arr1, arr2)
        np.testing.assert_array_equal(results[0], data * 2)
        np.testing.assert_array_equal(results[1], data + 2)

    def testExecuteNotFetch(self):
        data = np.random.random((5, 9))
        sess = Session.default_or_local()

        arr1 = mt.tensor(data, chunk_size=2) * 2

        with self.assertRaises(ValueError):
            sess.fetch(arr1)

        self.assertIsNone(arr1.execute(fetch=False))

        # modify result
        executor = sess._sess._executor
        executor.chunk_result[arr1.chunks[0].key] = data[:2, :2] * 3

        expected = data * 2
        expected[:2, :2] = data[:2, :2] * 3

        np.testing.assert_array_equal(arr1.execute(), expected)

    def testClosedSession(self):
        session = new_session()
        arr = mt.ones((10, 10))

        result = session.run(arr)

        np.testing.assert_array_equal(result, np.ones((10, 10)))

        session.close()
        with self.assertRaises(RuntimeError):
            session.run(arr)

        with self.assertRaises(RuntimeError):
            session.run(arr + 1)

    def testBoolIndexing(self):
        arr = mt.random.rand(10, 10, chunk_size=5)
        arr[3:8, 3:8] = mt.ones((5, 5))

        arr2 = arr[arr == 1]
        self.assertEqual(arr2.shape, (np.nan,))

        arr2.execute()
        self.assertEqual(arr2.shape, (25,))

        arr3 = arr2.reshape((5, 5))
        expected = np.ones((5, 5))
        np.testing.assert_array_equal(arr3.execute(), expected)

    def testArrayProtocol(self):
        arr = mt.ones((10, 20))

        result = np.asarray(arr)
        np.testing.assert_array_equal(result, np.ones((10, 20)))

        arr2 = mt.ones((10, 20))

        result = np.asarray(arr2, mt.bool_)
        np.testing.assert_array_equal(result, np.ones((10, 20), dtype=np.bool_))

        arr3 = mt.ones((10, 20)).sum()

        result = np.asarray(arr3)
        np.testing.assert_array_equal(result, np.asarray(200))

        arr4 = mt.ones((10, 20)).sum()

        result = np.asarray(arr4, dtype=np.float_)
        np.testing.assert_array_equal(result, np.asarray(200, dtype=np.float_))

    def testRandomExecuteInSessions(self):
        arr = mt.random.rand(20, 20)

        sess1 = new_session()
        res1 = sess1.run(arr)

        sess2 = new_session()
        res2 = sess2.run(arr)

        np.testing.assert_array_equal(res1, res2)

    def testFetch(self):
        sess = new_session()

        arr1 = mt.ones((10, 5), chunk_size=3)

        r1 = sess.run(arr1)
        r2 = sess.run(arr1)
        np.testing.assert_array_equal(r1, r2)

        executor = sess._sess._executor
        executor.chunk_result[arr1.chunks[0].key] = np.ones((3, 3)) * 2
        r3 = sess.run(arr1 + 1)
        np.testing.assert_array_equal(r3[:3, :3], np.ones((3, 3)) * 3)

        # rerun to ensure arr1's chunk results still exist
        r4 = sess.run(arr1 + 1)
        np.testing.assert_array_equal(r4[:3, :3], np.ones((3, 3)) * 3)

        arr2 = mt.ones((10, 5), chunk_size=3)
        r5 = sess.run(arr2)
        np.testing.assert_array_equal(r5[:3, :3], np.ones((3, 3)) * 2)

        r6 = sess.run(arr2 + 1)
        np.testing.assert_array_equal(r6[:3, :3], np.ones((3, 3)) * 3)

        # test fetch multiple tensors
        raw = np.random.rand(5, 10)
        arr1 = mt.ones((5, 10), chunk_size=5)
        arr2 = mt.tensor(raw, chunk_size=3)
        arr3 = mt.sum(arr2)

        sess.run(arr1, arr2, arr3)

        fetch1, fetch2, fetch3 = sess.fetch(arr1, arr2, arr3)
        np.testing.assert_array_equal(fetch1, np.ones((5, 10)))
        np.testing.assert_array_equal(fetch2, raw)
        np.testing.assert_almost_equal(fetch3, raw.sum())

        fetch1, fetch2, fetch3 = sess.fetch([arr1, arr2, arr3])
        np.testing.assert_array_equal(fetch1, np.ones((5, 10)))
        np.testing.assert_array_equal(fetch2, raw)
        np.testing.assert_almost_equal(fetch3, raw.sum())

    def testDecref(self):
        sess = new_session()

        arr1 = mt.ones((10, 5), chunk_size=3)
        arr2 = mt.ones((10, 5), chunk_size=3)
        sess.run(arr1)
        sess.run(arr2)
        sess.fetch(arr1)

        executor = sess._sess._executor

        self.assertEqual(len(executor.chunk_result), 4)  # 4 kinds of shapes
        del arr1
        self.assertEqual(len(executor.chunk_result), 4)
        del arr2
        self.assertEqual(len(executor.chunk_result), 0)
