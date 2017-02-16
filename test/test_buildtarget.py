# Copyright (C) 2016 Brian J. Stucky
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# Python imports.
from ontobuilder.buildtarget import BuildTarget
import unittest

# Java imports.


# Expected test results.
TARGET1_PRODUCTS = {
    'product 1': 'something'
}
COMBINED_PRODUCTS =  {
    'product 1': 'something',
    'product 2': 'something else'
}

# Define two dummy concrete build targets to test the build functionality.
class Target1(BuildTarget):
    def _isBuildRequired(self):
        return False
    def _run(self):
        return TARGET1_PRODUCTS

class Target2(BuildTarget):
    def _isBuildRequired(self):
        return True
    def _run(self):
        return {'product 2': 'something else'}


class TestBuildTarget(unittest.TestCase):
    """
    Tests the BuildTarget base class.
    """
    def setUp(self):
        pass

    def test_isBuildRequired(self):
        # Test single targets with no dependencies, one that requires a build
        # and one that does not.
        target1 = Target1()
        self.assertFalse(target1.isBuildRequired())
        target2 = Target2()
        self.assertTrue(target2.isBuildRequired())

        # Test a target that does not explicitly require a build, but with a
        # dependency that does.
        target1.addDependency(target2)
        self.assertTrue(target1.isBuildRequired())

        # Test a target that does require a build, but with a dependency that
        # does not.
        target1 = Target1()
        target2.addDependency(target1)
        self.assertTrue(target2.isBuildRequired())

        # Test a target that does not require a build, and with a dependency
        # that also does not.
        target2 = Target1()
        target1.addDependency(target2)
        self.assertFalse(target1.isBuildRequired())

    def test_run(self):
        # Test a single target with no dependencies.
        target1 = Target1()
        result = target1.run()
        self.assertEqual(TARGET1_PRODUCTS, result)

        # Test a single target with a dependency.
        target2 = Target2()
        target1.addDependency(target2)
        result = target1.run()
        self.assertEqual(COMBINED_PRODUCTS, result)

        # Test dependencies with conflicting build products.
        target2_2 = Target2()
        target1.addDependency(target2_2)
        with self.assertRaisesRegexp(
            RuntimeError, 'Unable to merge product returned from build target'
        ):
            target1.run()

        # Test a dependency with a build product that conflicts with the
        # dependent's build products.
        target1 = Target1()
        target2 = Target1()
        target1.addDependency(target2)
        with self.assertRaisesRegexp(
            RuntimeError,
            "key that duplicates one of its dependency's product name keys"
        ):
            target1.run()
