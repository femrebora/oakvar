def raise_break(__signal_number__, __stack_frame__):
    import os
    import platform
    import psutil
    pl = platform.platform()
    if pl.startswith("Windows"):
        pid = os.getpid()
        for child in psutil.Process(pid).children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        os.kill(pid, signal.SIGTERM)
    elif pl.startswith("Linux"):
        pid = os.getpid()
        for child in psutil.Process(pid).children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        os.kill(pid, signal.SIGTERM)
    elif pl.startswith("Darwin") or pl.startswith("macOS"):
        pid = os.getpid()
        for child in psutil.Process(pid).children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        os.kill(pid, signal.SIGTERM)


import signal
signal.signal(signal.SIGINT, raise_break)

from .base_converter import BaseConverter
if BaseConverter is None:
    raise NotImplemented
from .base_annotator import BaseAnnotator
if BaseAnnotator is None:
    raise NotImplemented
from .base_mapper import BaseMapper
if BaseMapper is None:
    raise NotImplemented
from .base_postaggregator import BasePostAggregator
if BasePostAggregator is None:
    raise NotImplemented
from .base_commonmodule import BaseCommonModule
if BaseCommonModule is None:
    raise NotImplemented
from .cli_report import CravatReport, fn_ov_report
if CravatReport is None or fn_ov_report is None:
    raise NotImplemented
from .config_loader import ConfigLoader
from .cravat_filter import CravatFilter
if CravatFilter is None:
    raise NotImplemented
from .cli_run import Cravat
if Cravat is None:
    raise NotImplemented
from .constants import crx_def
if crx_def is None:
    raise NotImplemented
from .exceptions import *
from . import constants
if constants is None:
    raise NotImplemented
from . import __main__ as cli
if cli is None:
    raise NotImplemented

wgs = None

def get_live_annotator(module_name):
    import os
    module = None
    ModuleClass = get_module(module_name)
    if ModuleClass is not None:
        module = ModuleClass(input_file="__dummy__", live=True)
        module.annotator_name = module_name
        module.annotator_dir = os.path.dirname(module.script_path)
        module.data_dir = os.path.join(module.module_dir, "data")
        module._open_db_connection()
        module.setup()
    return module


def get_live_mapper(module_name):
    import os
    module = None
    ModuleClass = get_module(module_name)
    if ModuleClass is not None:
        module = ModuleClass({
            "script_path":
            os.path.abspath(ModuleClass.script_path),
            "input_file":
            "__dummy__",
            "live":
            True,
        })
        module.base_setup()
    return module


def get_module(module_name):
    import os
    from .admin_util import get_local_module_info
    from .util import load_class
    ModuleClass = None
    config_loader = ConfigLoader()
    module_info = get_local_module_info(module_name)
    if module_info is not None:
        script_path = module_info.script_path
        ModuleClass = load_class(script_path)
        ModuleClass.script_path = script_path
        ModuleClass.module_name = module_name
        ModuleClass.module_dir = os.path.dirname(script_path)
        ModuleClass.conf = config_loader.get_module_conf(module_name)
    return ModuleClass


def get_wgs_reader(assembly="hg38"):
    ModuleClass = get_module(assembly + "wgs")
    if ModuleClass is None:
        wgs = None
    else:
        wgs = ModuleClass()
        wgs.setup()
    return wgs


class LiveAnnotator:

    def __init__(self, mapper="hg38", annotators=[]):
        self.live_annotators = {}
        self.load_live_modules(mapper, annotators)
        self.variant_uid = 1
        self.live_mapper = None

    def load_live_modules(self, mapper, annotator_names):
        from .admin_util import get_mic
        self.live_mapper = get_live_mapper(mapper)
        for module_name in get_mic().local.keys():
            if module_name in annotator_names:
                module = get_mic().local[module_name]
                if "secondary_inputs" in module.conf:
                    continue
                annotator = get_live_annotator(module.name)
                if annotator is None:
                    continue
                self.live_annotators[module.name] = annotator

    def clean_annot_dict(self, d):
        keys = d.keys()
        for key in keys:
            value = d[key]
            if value == "" or value == {}:
                d[key] = None
            elif type(value) is dict:
                d[key] = self.clean_annot_dict(value)
        if type(d) is dict:
            all_none = True
            for key in keys:
                if d[key] is not None:
                    all_none = False
                    break
            if all_none:
                d = None
        return d

    def annotate(self, crv):
        from .inout import AllMappingsParser
        from oakvar.constants import all_mappings_col_name

        if "uid" not in crv:
            crv["uid"] = self.variant_uid
            self.variant_uid += 1
        response = {}
        crx_data = None
        if self.live_mapper is not None:
            crx_data = self.live_mapper.map(crv)
            crx_data = self.live_mapper.live_report_substitute(crx_data)
            crx_data["tmp_mapper"] = AllMappingsParser(
                crx_data[all_mappings_col_name])
        for k, v in self.live_annotators.items():
            try:
                if crx_data is not None:
                    annot_data = v.annotate(input_data=crx_data)
                    annot_data = v.live_report_substitute(annot_data)
                    if annot_data == "" or annot_data == {}:
                        annot_data = None
                    elif type(annot_data) is dict:
                        annot_data = self.clean_annot_dict(annot_data)
                    response[k] = annot_data
            except Exception as _:
                import traceback

                traceback.print_exc()
                response[k] = None
        if crx_data is not None and "tmp_mapper" in crx_data:
            del crx_data["tmp_mapper"]
        if crx_data is not None:
            response["base"] = crx_data
        return response
