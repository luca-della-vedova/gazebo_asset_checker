import os
import fileinput
import argparse
import re
from enum import Enum
from glob import glob
from pathlib import Path
import xml.etree.ElementTree as ET


class Verbosity(Enum):
    ERR = 0
    WARN = 1
    INFO = 2

    # Comparison operator
    def __ge__(self, b):
        return self.value >= b

class AssetError:

    COLORMAP = {Verbosity.INFO : '\033[94m', Verbosity.WARN : '\033[93m', Verbosity.ERR : '\033[91m', 'end' : '\033[0m'}

    def __init__(self, severity, message):
        self.severity = severity
        self.message = message

    def __str__(self):
        return "\t" + self.COLORMAP[self.severity] + self.severity.name + ": " + self.message + self.COLORMAP['end']


class AssetChecker:

    def __init__(self, model_folder, autofix=False):
        full_dir = os.path.expanduser(model_folder)
        self.autofix = autofix
        self.model_dirs = glob(full_dir + "/*/")
        # Sort for prettiness
        self.model_dirs.sort()
        self.errors = {}
        self.num_fixes = 0

    def add_error(self, model_name, severity, message):
        if model_name not in self.errors:
            self.errors[model_name] = []
        self.errors[model_name].append(AssetError(severity, message))

    def check_model_name(self, model_name):
        # We are looking for CamelCase, so the string must have
        # both cases, no underscores and start with an uppercase
        valid = any(c.isupper() for c in model_name) and \
                any(c.islower() for c in model_name) and \
                '_' not in model_name and model_name[0].isupper()
        if not valid:
            self.add_error(model_name, Verbosity.ERR,
                           "Model name not CamelCase")

    def check_texture_name(self, filename):
        ALLOWED_TEXTURE_NAMES = ["Diffuse", "Normal", "Rough", "Metal"]
        # Make sure it is a legal texture name
        texture_end = filename.stem.rsplit('_', 1)[-1]
        if '_' not in filename.stem or \
                texture_end not in ALLOWED_TEXTURE_NAMES:
            return False
        return True

    def check_folder_structure(self, model_name, model_dir):
        self.check_root_folder_structure(model_name, model_dir)
        self.check_meshes_folder_structure(model_name, model_dir + 'meshes/')

    def check_meshes_folder_structure(self, model_name, mesh_dir):
        # Make sure the folder exists, error is added in root folder function
        if not os.path.exists(mesh_dir):
            return
        folders = [p for p in Path(mesh_dir).iterdir() if p.is_dir()]
        if len(folders) > 0:
            self.add_error(model_name, Verbosity.ERR,
                           "meshes folder contains subfolders")
        files = [p for p in Path(mesh_dir).iterdir() if p.is_file()]
        ALLOWED_EXTENSIONS = [".png", ".dae", ".mtl", ".obj"]
        for f in files:
            if f.suffix not in ALLOWED_EXTENSIONS:
                self.add_error(model_name, Verbosity.ERR, "Illegal extension "
                               "in meshes folder: " + f.suffix)
            elif f.suffix == ".png" and self.check_texture_name(f) is False:
                self.add_error(model_name, Verbosity.ERR,
                               "Illegal texture name: " + f.name)
            # TODO Iterate over all obj, make sure there is matching mtl

    def check_root_folder_structure(self, model_name, model_dir):
        # Root folder should only contain model.sdf and model.config files
        # and meshes subfolder
        all_items = [p for p in Path(model_dir).iterdir()]
        if len(all_items) > 3:
            self.add_error(model_name, Verbosity.ERR,
                           "Model folder contains more than three items")
        files = [p.name for p in all_items if p.is_file()]
        folders = [p.name for p in all_items if p.is_dir()]
        if "meshes" not in folders:
            self.add_error(model_name, Verbosity.ERR,
                           "Model missing mesh subfolder")
        if "model.sdf" not in files:
            self.add_error(model_name, Verbosity.ERR,
                           "Model missing model.sdf")
        if "model.config" not in files:
            self.add_error(model_name, Verbosity.ERR,
                           "Model missing model.config")

    def fix_mtl(self, mtl_file):
        for line in fileinput.FileInput(mtl_file, inplace=1):
            if 'Kd' in line and 'map_' not in line:
                # Substitute all floating point values with 0.800000
                # TODO match number of decimal digits
                line = re.sub("[+-]?([0-9]*[.])?[0-9]+", "0.800000", line)
            print(line, end='')
        self.num_fixes += 1

    def check_mtl(self, model_name, mesh_dir):
        if not os.path.exists(mesh_dir):
            return
        mtl_files = [p for p in Path(mesh_dir).iterdir() if p.suffix == '.mtl']
        for mtl_file in mtl_files:
            valid = True
            with open(mtl_file) as f:
                for line in f.readlines():
                    if 'Kd' in line and 'map_' not in line:
                        kd_vals = line.split(' ')[-3:]
                        kd_vals = [float(val.strip()) for val in kd_vals]
                        for val in kd_vals:
                            # We can go exact equality here
                            if val != 0.8:
                                valid = False
            if not valid:
                self.add_error(model_name, Verbosity.ERR,
                               "Kd value in mtl different from default of 0.8")
            if not valid and self.autofix is True:
                self.fix_mtl(mtl_file)

    def check_model_config(self, model_name, model_dir):
        # Checks .config file
        filepath = model_dir + 'model.config'
        if not os.path.exists(filepath):
            return
        tree = ET.parse(filepath)
        # Will throw if nodes are non existent, assumes valid template
        author_node = tree.getroot().find('author')
        if author_node.find('name').text in [None, "name"]:
            # Author name empty
            self.add_error(model_name, Verbosity.WARN,
                           "Author name field in .config file is empty")
        if author_node.find('email').text is None:
            # Author email empty
            self.add_error(model_name, Verbosity.WARN,
                           "Author email field in .config file is empty")
        if tree.getroot().find('description').text.strip() in \
                [None, "Description of the model"]:
            # Model description empty
            self.add_error(model_name, Verbosity.ERR,
                           "Model description in .config file is empty")

    def check_model(self, model_dir):
        model_name = model_dir.rstrip('/').split('/')[-1]
        self.check_model_name(model_name)
        self.check_folder_structure(model_name, model_dir)
        # Rest of checks...
        self.check_mtl(model_name, model_dir + 'meshes/')
        self.check_model_config(model_name, model_dir)

        if model_name in self.errors:
            return self.errors[model_name]
        return None

    def check_models(self):
        for model_dir in self.model_dirs:
            self.check_model(model_dir)

    def print_report(self, verbose):
        num_errors = 0
        for name, errors in self.errors.items():
            if verbose >= Verbosity.ERR.value:
                print("Issues found in model " + name)
                for err in errors:
                    if verbose >= err.severity.value:
                        print(err)
                        num_errors += 1
        print(str(len(self.model_dirs)) + " assets checked, " +
              str(num_errors) + " errors found")
        print(str(self.num_fixes) + " errors fixed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check that gazebo models and meshes follow "
            "a convention that will reduce risk of issues and make rendering results more consistent")
    parser.add_argument('model_paths', metavar='path', type=str, nargs='+',
                    help='Path where models are stored')
    parser.add_argument('-f', dest='autofix', action='store_const',
                    const=True, default=False,
                    help='Attempt to fix issues (experimental)')
    parser.add_argument('-v', dest='verbose', action='count',
                    default=-1,
                    help='Verbosity level (INFO - WARN - ERR)')
    args = parser.parse_args()
    for path in args.model_paths:
        checker = AssetChecker(path, autofix=args.autofix)
        checker.check_models()
        checker.print_report(verbose=args.verbose)
