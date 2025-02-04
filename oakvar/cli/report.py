from ..decorators import cli_func
from ..decorators import cli_entry
from ..base.report_filter import DEFAULT_SERVER_DEFAULT_USERNAME
import sys
import nest_asyncio
from typing import List
from typing import Any

nest_asyncio.apply()
if sys.platform == "win32" and sys.version_info >= (3, 8):
    from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy

    set_event_loop_policy(WindowsSelectorEventLoopPolicy())


class BaseReporter:
    def __init__(self, args):
        from ..util.admin_util import get_user_conf
        self.cf = None
        self.filtertable = "filter"
        self.colinfo = {}
        self.colnos = {}
        self.var_added_cols = []
        self.summarizing_modules = []
        self.columngroups = {}
        self.column_subs = {}
        self.column_sub_allow_partial_match = {}
        self.colname_conversion = {}
        self.warning_msgs = []
        self.colnames_to_display = {}
        self.cols_to_display = {}
        self.colnos_to_display = {}
        self.display_select_columns = {}
        self.extracted_cols = {}
        self.conn = None
        self.levels_to_write = None
        self.args = None
        self.dbpath = None
        self.filterpath = None
        self.filtername = None
        self.filterstring = None
        self.filtersql = None
        self.filter = None
        self.confs = {}
        self.output_dir = None
        self.savepath = None
        self.conf = None
        self.module_name = None
        self.module_conf = None
        self.report_types = None
        self.output_basename = None
        self.status_fpath = None
        self.nogenelevelonvariantlevel = None
        self.status_writer = None
        self.concise_report = None
        self.extract_columns_multilevel = {}
        self.logger = None
        self.error_logger = None
        self.unique_excs = None
        self.mapper_name = None
        self.level = None
        self.no_log = False
        self.colcount = {}
        self.columns = {}
        self.conns = []
        self.gene_summary_datas = {}
        self.priority_colgroupnames = (get_user_conf() or {}).get("report_module_order", [
            "base",
            "tagsampler",
            "gencode",
            "hg38",
            "hg19",
            "hg18",
        ])
        self.modules_to_add_to_base = []
        self.user = DEFAULT_SERVER_DEFAULT_USERNAME
        self.parse_cmd_args(args)
        self._setup_logger()

    async def exec_db(self, func, *args, **kwargs):
        from ..exceptions import DatabaseConnectionError

        conn = await self.get_db_conn()
        if not conn:
            raise DatabaseConnectionError(self.module_name)
        cursor = await conn.cursor()
        try:
            ret = await func(*args, conn=conn, cursor=cursor, **kwargs)
        except:
            await cursor.close()
            raise
        await cursor.close()
        return ret

    def parse_cmd_args(self, args):
        import sqlite3
        from os.path import dirname
        from os.path import basename
        from os.path import join
        from os.path import exists
        import json
        from ..module.local import get_module_conf
        from os.path import abspath
        from ..system import consts
        from ..exceptions import WrongInput

        if not args:
            return
        if args.get("md"):
            consts.custom_modules_dir = args.get("md")
        self.dbpath = args.get("dbpath")
        if not exists(self.dbpath):
            raise WrongInput(msg=self.dbpath)
        try:
            with sqlite3.connect(self.dbpath) as db:
                db.execute("select * from info")
        except:
            raise WrongInput(msg=f"{self.dbpath} is not an OakVar database")
        self.filterpath = args.get("filterpath")
        self.filtername = args.get("filtername")
        self.filterstring = args.get("filterstring")
        self.filtersql = args.get("filtersql")
        self.filter = args.get("filter")
        self.output_dir = args.get("output_dir")
        self.module_name = args.get("module_name")
        self.report_types = args.get("reports")
        self.savepath = args.get("savepath")
        if self.output_dir:
            self.output_dir = dirname(self.dbpath)
        if not self.output_dir:
            self.output_dir = abspath(".")
        if self.savepath and dirname(self.savepath) == "":
            self.savepath = join(self.output_dir, self.savepath)
        self.module_conf = get_module_conf(self.module_name, module_type="reporter")
        self.confs = {}
        self.conf = args.get("conf")
        if self.conf:
            if self.module_name in self.conf:
                self.confs.update(self.conf[self.module_name])
            else:
                self.confs.update(self.conf)
        # confs update from confs
        confs = args.get("confs")
        if confs:
            confs = confs.lstrip("'").rstrip("'").replace("'", '"')
            if not self.confs:
                self.confs = json.loads(confs)
            else:
                self.confs.update(json.loads(confs))
        self.output_basename = basename(self.dbpath)[:-7]
        status_fname = "{}.status.json".format(self.output_basename)
        self.status_fpath = join(self.output_dir, status_fname)
        self.nogenelevelonvariantlevel = args.get("nogenelevelonvariantlevel", False)
        inputfiles = args.get("inputfiles")
        dbpath = args.get("dbpath")
        if not inputfiles and dbpath:
            db = sqlite3.connect(dbpath)
            c = db.cursor()
            q = 'select colval from info where colkey="_input_paths"'
            c.execute(q)
            r = c.fetchone()
            if r is not None:
                args["inputfiles"] = []
                s = r[0]
                if " " in s:
                    s = s.replace("'", '"')
                s = s.replace("\\", "\\\\\\\\")
                s = json.loads(s)
                for k in s:
                    input_path = s[k]
                    args["inputfiles"].append(input_path)
            c.close()
            db.close()
        self.inputfiles = args.get("inputfiles")
        self.status_writer = args.get("status_writer")
        self.concise_report = args.get("concise_report")
        if args.get("cols"):
            self.extract_columns_multilevel = {}
            for level in ["variant", "gene", "sample", "mapping"]:
                self.extract_columns_multilevel[level] = args.get("cols")
        else:
            self.extract_columns_multilevel = self.get_standardized_module_option(
                self.confs.get("extract_columns", {})
            )
        self.add_summary = not args.get("no_summary", False)
        self.args = args


    def should_write_level(self, level):
        if self.levels_to_write is None:
            return True
        elif level in self.levels_to_write:
            return True
        else:
            return False

    async def connect_db (self, dbpath=None):
        _ = dbpath

    async def prep(self, user=DEFAULT_SERVER_DEFAULT_USERNAME):
        await self.set_dbpath()
        await self.connect_db(dbpath=self.dbpath)
        await self.load_filter(user=user)

    async def check_result_db_for_mandatory_cols(self):
        from ..exceptions import ResultMissingMandatoryColumnError

        conn = await self.get_db_conn()
        if not conn:
            return
        if not self.module_conf:
            await conn.close()
            return
        mandatory_columns = self.module_conf.get("mandatory_columns")
        if not mandatory_columns:
            await conn.close()
            return
        cursor = await conn.cursor()
        db_col_names = []
        for level in ["variant", "gene"]:
            q = f"select col_name from {level}_header"
            await cursor.execute(q)
            col_names = await cursor.fetchall()
            db_col_names.extend([v[0] for v in col_names])
        missing_col_names = []
        for col_name in mandatory_columns:
            if col_name not in db_col_names:
                missing_col_names.append(col_name)
        await conn.close()
        if missing_col_names:
            cols = ", ".join(missing_col_names)
            raise ResultMissingMandatoryColumnError(self.dbpath, cols)

    def _setup_logger(self):
        if self.module_name is None:
            return
        import logging

        if getattr(self, "no_log", False):
            return
        try:
            self.logger = logging.getLogger(self.module_name)
        except Exception as e:
            self._log_exception(e)
        self.error_logger = logging.getLogger("err." + self.module_name)
        self.unique_excs = []

    async def get_db_conn(self):
        import aiosqlite

        if self.dbpath is None:
            return None
        if not self.conn:
            self.conn = await aiosqlite.connect(self.dbpath)
            self.conns.append(self.conn)
        return self.conn

    def _log_exception(self, e, halt=True):
        if halt:
            raise e
        elif self.logger:
            self.logger.exception(e)

    def substitute_val(self, level, row):
        from json import loads
        from json import dumps

        for sub in self.column_subs.get(level, []):
            col_name = f"{sub.module}__{sub.col}"
            value = row[col_name]
            if value is None or value == "" or value == "{}":
                continue
            if (level == "variant" and sub.module == "base" and sub.col == "all_mappings"):
                mappings = loads(value)
                for gene in mappings:
                    for i in range(len(mappings[gene])):
                        sos = mappings[gene][i][2].split(",")
                        sos = [sub.subs.get(so, so) for so in sos]
                        mappings[gene][i][2] = ",".join(sos)
                value = dumps(mappings)
            elif level == "gene" and sub.module == "base" and sub.col == "all_so":
                vals = []
                for i, so_count in enumerate(value.split(",")):
                    so = so_count[:3]
                    so = sub.subs.get(so, so)
                    so_count = so + so_count[3:]
                    vals.append(so_count)
                value = ",".join(vals)
            else:
                value = sub.subs.get(value, value)
            row[col_name] = value
        return row

    def get_extracted_header_columns(self, level):
        cols = []
        for col in self.colinfo[level]["columns"]:
            if col["col_name"] in self.colnames_to_display[level]:
                cols.append(col)
        return cols

    def get_db_col_name(self, mi, col):
        if mi.name in ["gencode", "hg38", "tagsampler"]:
            grp_name = "base"
        else:
            grp_name = mi.name
        return f"{grp_name}__{col['name']}"

    def col_is_categorical(self, col):
        return "category" in col and col["category"] in ["single", "multi"]

    async def do_gene_level_summary(self, add_summary=True):
        _ = add_summary
        self.gene_summary_datas = {}
        if not self.summarizing_modules:
            return self.gene_summary_datas
        for mi, module_instance, summary_cols in self.summarizing_modules:
            gene_summary_data = await module_instance.get_gene_summary_data(self.cf)
            self.gene_summary_datas[mi.name] = [gene_summary_data, summary_cols]
            columns = self.colinfo["gene"]["columns"]
            for col in summary_cols:
                if not self.col_is_categorical(col):
                    continue
                colinfo_col = {}
                colno = None
                for i in range(len(columns)):
                    if columns[i]["col_name"] == self.get_db_col_name(mi, col):
                        colno = i
                        break
                cats = []
                for hugo in gene_summary_data:
                    val = gene_summary_data[hugo][col["name"]]
                    repsub = colinfo_col.get("reportsub", [])
                    if len(repsub) > 0:
                        if val in repsub:
                            val = repsub[val]
                    if val not in cats:
                        cats.append(val)
                if colno is not None:
                    columns[colno]["col_cats"] = cats

    async def store_mapper(self, conn=None, cursor=None):
        from ..exceptions import DatabaseConnectionError

        if conn is None or cursor is None:
            raise DatabaseConnectionError(self.module_name)
        q = 'select colval from info where colkey="_mapper"'
        await cursor.execute(q)
        r = await cursor.fetchone()
        if r is None:
            self.mapper_name = "hg38"
        else:
            self.mapper_name = r[0].split(":")[0]

    def write_log(self, msg):
        if not self.logger:
            return
        self.logger.info(msg)

    def write_status(self, msg):
        if not self.status_writer or (self.args and self.args.get("do_not_change_status")):
            return
        self.status_writer.queue_status_update("status", msg)

    def log_run_start(self):
        from time import asctime, localtime
        import oyaml as yaml
        self.write_log("started: %s" % asctime(localtime(self.start_time)))
        if self.cf and self.cf.filter:
            self.write_log(f"filter:\n{yaml.dump(self.filter)}")
        if self.module_conf:
            self.write_status(f"Started {self.module_conf['title']} ({self.module_name})")

    async def get_levels_to_run(self, tab: str) -> List[str]:
        if not self.cf:
            return []
        if tab == "all":
            levels = await self.cf.exec_db(self.cf.get_result_levels)
        else:
            levels = [tab]
        if type(levels) is not list:
            return []
        if not levels:
            return []
        return levels

    async def run(self, tab="all", add_summary=None, pagesize=None, page=None, make_filtered_table=True, user=DEFAULT_SERVER_DEFAULT_USERNAME, dictrow=False):
        from ..exceptions import SetupError
        from time import time
        from time import asctime
        from time import localtime

        _ = user
        try:
            if add_summary is None:
                add_summary = self.add_summary
            self.dictrow = dictrow
            await self.prep()
            if not self.args or not self.cf or not self.logger:
                raise SetupError(self.module_name)
            self.start_time = time()
            ret = None
            tab = tab or self.args.get("level", "all")
            self.log_run_start()
            if self.setup() == False:
                await self.close_db()
                raise SetupError(self.module_name)
            self.ftable_uid = await self.cf.make_ftables_and_ftable_uid(make_filtered_table=make_filtered_table)
            self.levels = await self.get_levels_to_run(tab)
            for level in self.levels:
                self.level = level
                await self.make_col_infos(add_summary=add_summary)
                await self.write_data(level, pagesize=pagesize, page=page, make_filtered_table=make_filtered_table, add_summary=add_summary)
            await self.close_db()
            if self.module_conf:
                self.write_status(f"Finished {self.module_conf['title']} ({self.module_name})")
            end_time = time()
            if not (hasattr(self, "no_log") and self.no_log):
                self.logger.info("finished: {0}".format(asctime(localtime(end_time))))
                run_time = end_time - self.start_time
                self.logger.info("runtime: {0:0.3f}".format(run_time))
            ret = self.end()
        except Exception as e:
            await self.close_db()
            raise e
        return ret

    async def write_data(self, level, add_summary=True, pagesize=None, page=None, make_filtered_table=True):
        from ..exceptions import SetupError

        _ = make_filtered_table
        if self.should_write_level(level) == False:
            return
        if not await self.exec_db(self.table_exists, level):
            return
        if not self.cf or not self.args:
            raise SetupError(self.module_name)
        if add_summary and self.level == "gene":
            await self.do_gene_level_summary(add_summary=add_summary)
        self.write_preface(level)
        self.extracted_cols[level] = self.get_extracted_header_columns(level)
        self.write_header(level)
        self.hugo_colno = self.colnos[level].get("base__hugo", None)
        datacols = await self.cf.exec_db(self.cf.get_variant_data_cols)
        #self.ftable_uid = await self.cf.make_ftables_and_ftable_uid(make_filtered_table=make_filtered_table)
        total_norows = await self.cf.exec_db(self.cf.get_ftable_num_rows, level=level, uid=self.ftable_uid, ftype=level)
        if datacols is None or total_norows is None:
            return
        self.sample_newcolno = None
        if level == "variant" and self.args.get("separatesample"):
            self.write_variant_sample_separately = True
            self.sample_newcolno = self.colnos["variant"]["base__samples"]
        else:
            self.write_variant_sample_separately = False
        datarows_iter = await self.cf.get_level_data_iterator(level, page=page, pagesize=pagesize)
        if not datarows_iter:
            return
        row_count = 0
        for datarow in datarows_iter:
            datarow = dict(datarow)
            if datarow is None:
                continue
            if level == "gene" and add_summary:
                await self.add_gene_summary_data_to_gene_level(datarow)
            if level == "variant":
                await self.add_gene_level_data_to_variant_level(datarow)
            #datarow = self.reorder_datarow(level, datarow)
            datarow = self.substitute_val(level, datarow)
            self.stringify_all_mapping(level, datarow)
            self.escape_characters(datarow)
            self.write_row_with_samples_separate_or_not(datarow)
            row_count += 1
            if pagesize and row_count == pagesize:
                break

    def write_row_with_samples_separate_or_not(self, datarow):
        col_name = "base__samples"
        if self.write_variant_sample_separately:
            samples = datarow[col_name]
            if samples:
                samples = samples.split(";")
                for sample in samples:
                    sample_datarow = datarow
                    sample_datarow[col_name] = sample
                    self.write_table_row(self.get_extracted_row(sample_datarow))
            else:
                self.write_table_row(self.get_extracted_row(datarow))
        else:
            self.write_table_row(self.get_extracted_row(datarow))

    def escape_characters(self, datarow):
        for k, v in datarow.items():
            if isinstance(v, str) and "\n" in v:
                datarow[k] = v.replace("\n", "%0A")

    def stringify_all_mapping(self, level, datarow):
        from json import loads
        if hasattr(self, "keep_json_all_mapping") == True or level != "variant":
            return
        col_name = "base__all_mappings"
        all_map = loads(datarow[col_name])
        newvals = []
        for hugo in all_map:
            for maprow in all_map[hugo]:
                [protid, protchange, so, transcript, rnachange] = maprow
                if protid == None:
                    protid = "(na)"
                if protchange == None:
                    protchange = "(na)"
                if rnachange == None:
                    rnachange = "(na)"
                newval = (
                    transcript
                    + ":"
                    + hugo
                    + ":"
                    + protid
                    + ":"
                    + so
                    + ":"
                    + protchange
                    + ":"
                    + rnachange
                )
                newvals.append(newval)
        newvals.sort()
        newcell = "; ".join(newvals)
        datarow[col_name] = newcell

    def reorder_datarow(self, level, datarow):
        new_datarow = []
        colnos = self.colnos[level]
        for column in self.colinfo[level]["columns"]:
            col_name = column["col_name"]
            #col_name = self.colname_conversion[level].get(col_name, col_name)
            colno = colnos[col_name]
            value = datarow[colno]
            new_datarow.append(value)
        return new_datarow

    async def add_gene_summary_data_to_gene_level(self, datarow):
        hugo = datarow["base__hugo"]
        for mi, _, _ in self.summarizing_modules:
            module_name = mi.name
            [gene_summary_data, cols] = self.gene_summary_datas[module_name]
            grp_name = "base" if self.should_be_in_base(module_name) else module_name
            if (
                hugo in gene_summary_data
                and gene_summary_data[hugo] is not None
                and len(gene_summary_data[hugo]) == len(cols)
            ):
                datarow.update(
                    {f"{grp_name}__{col['name']}": gene_summary_data[hugo][col["name"]] for col in cols}
                )
            else:
                datarow.update({f"{grp_name}__{col['name']}": None for col in cols})

    async def add_gene_level_data_to_variant_level(self, datarow):
        if self.nogenelevelonvariantlevel or self.hugo_colno is None or not self.cf:
            return
        generow = await self.cf.exec_db(self.cf.get_gene_row, datarow["base__hugo"])
        if generow is None:
            datarow.update({col: None for col in self.var_added_cols})
        else:
            datarow.update({col: generow[col] for col in self.var_added_cols})

    async def get_variant_colinfo(self, add_summary=True):
        try:
            await self.prep()
            if self.setup() == False:
                await self.close_db()
                return None
            self.levels = await self.get_levels_to_run("all")
            await self.make_col_infos(add_summary=add_summary)
            return self.colinfo
        except:
            await self.close_db()
            return None

    def setup(self):
        pass

    def end(self):
        pass

    def write_preface(self, __level__):
        pass

    def write_header(self, __level__):
        pass

    def write_table_row(self, __row__):
        pass

    def get_extracted_row(self, row):
        if self.dictrow:
            filtered_row = {col: row[col] for col in self.cols_to_display[self.level]}
        else:
            filtered_row = [row[col] for col in self.colnames_to_display[self.level]]
        return filtered_row

    def add_to_colnames_to_display(self, level, column):
        """
        include columns according to --cols option
        """
        col_name = column["col_name"]
        if (
            level in self.extract_columns_multilevel
            and len(self.extract_columns_multilevel[level]) > 0
        ):
            if col_name in self.extract_columns_multilevel[level]:
                incl = True
            else:
                incl = False
        elif self.concise_report:
            if "col_hidden" in column and column["col_hidden"] == True:
                incl = False
            else:
                incl = True
        else:
            incl = True
        if incl and col_name not in self.colnames_to_display[level]:
            #if self.should_be_in_base(col_name):
            #    col_name = self.change_colname_to_base(col_name)
            self.colnames_to_display[level].append(col_name)

    def change_colname_to_base(self, col_name):
        fieldname = self.get_field_name(col_name)
        return f"base__{fieldname}"

    async def make_sorted_column_groups(self, level, conn=Any):
        cursor = await conn.cursor()
        self.columngroups[level] = []
        sql = f"select name, displayname from {level}_annotator order by name"
        await cursor.execute(sql)
        rows = await cursor.fetchall()
        for row in rows:
            (name, displayname) = row
            if name == "base":
                self.columngroups[level].append({"name": name, "displayname": displayname, "count": 0})
                break
        for row in rows:
            (name, displayname) = row
            if name in self.modules_to_add_to_base:
                self.columngroups[level].append({"name": name, "displayname": displayname, "count": 0})
        for row in rows:
            (name, displayname) = row
            if name != "base" and name not in self.modules_to_add_to_base:
                self.columngroups[level].append({"name": name, "displayname": displayname, "count": 0})

    async def make_coldefs(self, level, conn=Any, where=None):
        from ..util.inout import ColumnDefinition
        if not conn:
            return
        cursor = await conn.cursor()
        header_table = f"{level}_header"
        coldefs = []
        sql = f"select col_name, col_def from {header_table}"
        if where:
            sql += f" where {where}"
        await cursor.execute(sql)
        rows = await cursor.fetchall()
        for row in rows:
            col_name, coljson = row
            group_name = col_name.split("__")[0]
            if group_name == "base" or group_name in self.modules_to_add_to_base:
                coldef = ColumnDefinition({})
                coldef.from_json(coljson)
                coldef.level = level
                coldef = await self.gather_col_categories(level, coldef, conn)
                coldefs.append(coldef)
        for row in rows:
            col_name, coljson = row
            group_name = col_name.split("__")[0]
            if group_name == "base" or group_name in self.modules_to_add_to_base:
                continue
            coldef = ColumnDefinition({})
            coldef.from_json(coljson)
            coldef.level = level
            coldef = await self.gather_col_categories(level, coldef, conn)
            coldefs.append(coldef)
        return coldefs

    async def gather_col_categories(self, level, coldef, conn):
        cursor = await conn.cursor()
        if not coldef.category in ["single", "multi"] or len(coldef.categories) > 0:
            return coldef
        sql = f"select distinct {coldef.name} from {level}"
        await cursor.execute(sql)
        rs = await cursor.fetchall()
        for r in rs:
            coldef.categories.append(r[0])
        return coldef

    async def make_columns_colnos_colnamestodisplay_columngroup(self, level, coldefs):
        self.columns[level] = []
        self.colnos[level] = {}
        self.colcount[level] = 0
        for coldef in coldefs:
            self.colnos[level][coldef.name] = self.colcount[level]
            self.colcount[level] += 1
            [colgrpname, _] = self.get_group_field_names(coldef.name)
            column = coldef.get_colinfo()
            self.columns[level].append(column)
            self.add_to_colnames_to_display(level, column)
            for columngroup in self.columngroups[level]:
                if columngroup["name"] == colgrpname:
                    columngroup["count"] += 1

    async def get_gene_level_modules_to_add_to_variant_level(self, conn):
        cursor = await conn.cursor()
        q = "select name from gene_annotator"
        await cursor.execute(q)
        gene_annotators = [v[0] for v in await cursor.fetchall()]
        modules_to_add = [m for m in gene_annotators if m != "base"]
        return modules_to_add

    async def add_gene_level_displayname_to_variant_level_columngroups(self, module_name, coldefs, conn):
        cursor = await conn.cursor()
        q = 'select displayname from gene_annotator where name=?'
        await cursor.execute(q, (module_name,))
        r = await cursor.fetchone()
        displayname = r[0]
        self.columngroups["variant"].append(
            {"name": module_name, "displayname": displayname, "count": len(coldefs)}
        )

    async def add_gene_level_columns_to_variant_level(self, conn):
        if not await self.exec_db(self.table_exists, "gene"):
            return
        modules_to_add = await self.get_gene_level_modules_to_add_to_variant_level(conn)
        for module_name in modules_to_add:
            module_prefix = f"{module_name}__"
            gene_coldefs = await self.make_coldefs("gene", conn=conn, where=f"col_name like '{module_prefix}%'")
            if not gene_coldefs:
                continue
            await self.add_gene_level_displayname_to_variant_level_columngroups(module_name, gene_coldefs, conn)
            for gene_coldef in gene_coldefs:
                self.colnos["variant"][gene_coldef.name] = self.colcount["variant"]
                self.colcount["variant"] += 1
                gene_column = gene_coldef.get_colinfo()
                self.columns["variant"].append(gene_column)
                self.add_to_colnames_to_display("variant", gene_column)
                self.var_added_cols.append(gene_coldef.name)

    async def add_gene_level_summary_columns(self, add_summary=True, conn=Any, cursor=Any):
        from ..exceptions import ModuleLoadingError
        from ..module.local import get_local_module_infos_of_type
        from ..module.local import get_local_module_info
        from ..util.util import load_class
        from ..util.util import quiet_print
        from ..util.inout import ColumnDefinition
        from os.path import dirname
        _ = conn
        if not add_summary:
            return
        q = "select name from variant_annotator"
        await cursor.execute(q)
        done_var_annotators = [v[0] for v in await cursor.fetchall()]
        self.summarizing_modules = []
        local_modules = get_local_module_infos_of_type("annotator")
        local_modules.update(get_local_module_infos_of_type("postaggregator"))
        summarizer_module_names = []
        for module_name in done_var_annotators:
            if module_name == self.mapper_name or module_name in [
                "base",
                "hg38",
                "hg19",
                "hg18",
                "extra_vcf_info",
                "extra_variant_info",
                "original_input"
            ]:
                continue
            if module_name not in local_modules:
                if module_name != "original_input":
                    quiet_print(
                        "            [{}] module does not exist in the system. Gene level summary for this module is skipped.".format(
                            module_name
                        ),
                        self.args,
                    )
                continue
            module = local_modules[module_name]
            if "can_summarize_by_gene" in module.conf:
                summarizer_module_names.append(module_name)
        local_modules[self.mapper_name] = get_local_module_info(self.mapper_name)
        summarizer_module_names = [self.mapper_name] + summarizer_module_names
        for module_name in summarizer_module_names:
            if not module_name:
                continue
            mi = local_modules[module_name]
            if not mi:
                continue
            sys.path = sys.path + [dirname(mi.script_path)]
            annot_cls = None
            if mi.name in done_var_annotators or mi.name == self.mapper_name:
                annot_cls = load_class(mi.script_path)
            if not annot_cls:
                raise ModuleLoadingError(mi.name)
            cmd = {
                "script_path": mi.script_path,
                "input_file": "__dummy__",
                "output_dir": self.output_dir,
            }
            annot = annot_cls(cmd)
            cols = mi.conf["gene_summary_output_columns"]
            columngroup = {
                "name": mi.name,
                "displayname": mi.title,
                "count": len(cols),
            }
            level = "gene"
            self.columngroups[level].append(columngroup)
            for col in cols:
                coldef = ColumnDefinition(col)
                if self.should_be_in_base(mi.name):
                    coldef.name = f"base__{coldef.name}"
                else:
                    coldef.name = f"{mi.name}__{coldef.name}"
                coldef.genesummary = True
                column = coldef.get_colinfo()
                self.columns[level].append(column)
                self.add_to_colnames_to_display(level, column)
                self.colnos[level][coldef.name] = len(self.colnos[level])
            self.summarizing_modules.append([mi, annot, cols])

    def find_col_or_colgroup_by_name(self, l, name):
        for el in l:
            if el["name"] == name:
                return el
        return None

    def get_colgroup_by_name(self, colgroups, name):
        for colgroup in colgroups:
            if colgroup["name"] == name:
                return colgroup
        return None

    async def place_priority_col_groups_first(self, level):
        colgrps = self.columngroups[level]
        newcolgrps = []
        # Places priority col groups first, as defined in priority_colgroupnames. Merges
        # mapper and tagsampler with base group.
        base_colgroup_no = self.priority_colgroupnames.index("base")
        for priority_colgrpname in self.priority_colgroupnames:
            colgrp = self.find_col_or_colgroup_by_name(colgrps, priority_colgrpname)
            if not colgrp:
                continue
            if self.should_be_in_base(colgrp["name"]):
                newcolgrps[base_colgroup_no]["count"] += colgrp["count"]
            else:
                newcolgrps.append(colgrp)
            colgrps.remove(colgrp)
        # place the rest of col groups.
        for colgroup in colgrps:
            newcolgrps.append(colgroup)
        # assigns last column number.
        last_colpos = 0
        for colgrp in newcolgrps:
            new_last_colpos = last_colpos + colgrp["count"]
            colgrp["lastcol"] = new_last_colpos
            last_colpos = new_last_colpos
        self.columngroups[level] = newcolgrps

    def should_be_in_base(self, name):
        if "__" in name:
            name = self.get_group_name(name)
        return name in self.modules_to_add_to_base

    def get_group_field_names(self, col_name):
        return col_name.split("__")

    def get_group_name(self, col_name):
        return self.get_group_field_names(col_name)[0]

    def get_field_name(self, col_name):
        return self.get_group_field_names(col_name)[1]

    async def order_columns_to_match_col_groups(self, level):
        self.colname_conversion[level] = {}
        new_columns = []
        new_colnos = {}
        new_colno = 0
        new_colnames_to_display = []
        for colgrp_to_find in self.columngroups[level]:
            group_name_to_find = colgrp_to_find["name"]
            for col in self.columns[level]:
                col_name = col["col_name"]
                old_col_name = col_name
                group_name = self.get_group_name(col_name)
                if group_name_to_find == "base" and self.should_be_in_base(group_name):
                    new_col_name = self.change_colname_to_base(col_name)
                    col["col_name"] = new_col_name
                    group_name = "base"
                    self.colname_conversion[level][new_col_name] = old_col_name
                col_name = col["col_name"]
                if group_name == group_name_to_find:
                    new_columns.append(col)
                    new_colnos[col_name] = new_colno
                    if col_name in self.colnames_to_display[level]:
                        new_colnames_to_display.append(col_name)
                    new_colno += 1
        self.columns[level] = new_columns
        self.colnos[level] = new_colnos
        self.colnames_to_display[level] = new_colnames_to_display

    async def make_report_sub(self, level, conn):
        from json import loads
        from types import SimpleNamespace
        if not level in ["variant", "gene"]:
            return
        reportsubtable = f"{level}_reportsub"
        if not await self.exec_db(self.table_exists, reportsubtable):
            return
        cursor = await conn.cursor()
        q = f"select * from {reportsubtable}"
        await cursor.execute(q)
        reportsub = {r[0]: loads(r[1]) for r in await cursor.fetchall()}
        self.column_subs[level] = []
        for i, column in enumerate(self.columns[level]):
            module_name, field_name = self.get_group_field_names(column["col_name"])
            if module_name == self.mapper_name:
                module_name = "base"
            if module_name in reportsub and field_name in reportsub[module_name]:
                self.column_subs[level].append(
                    SimpleNamespace(
                        module=module_name,
                        col=field_name,
                        index=i,
                        subs=reportsub[module_name][field_name],
                    )
                )
                self.columns[level][i]["reportsub"] = reportsub[module_name][field_name]

    def set_display_select_columns(self, level):
        if self.extract_columns_multilevel.get(level, {}) or self.concise_report:
            self.display_select_columns[level] = True
        else:
            self.display_select_columns[level] = False

    def set_cols_to_display(self, level):
        self.cols_to_display[level] = []
        self.colnos_to_display[level] = []
        colno = 0
        for col in self.columns[level]:
            col_name = col["col_name"]
            if col_name in self.colnames_to_display[level]:
                self.cols_to_display[level].append(col_name)
                self.colnos_to_display[level].append(colno)
            colno += 1

    async def make_col_infos(self, add_summary=True):
        prev_level = self.level
        for level in self.levels:
            self.level = level
            await self.exec_db(self.make_col_info, level, add_summary=add_summary)
        self.level = prev_level

    async def make_col_info(self, level: str, add_summary=True, conn=Any, cursor=Any):
        _ = cursor
        if not level or not await self.exec_db(self.table_exists, level):
            return
        await self.exec_db(self.store_mapper)
        self.colnames_to_display[level] = []
        self.modules_to_add_to_base = [self.mapper_name, "tagsampler"]
        await self.make_sorted_column_groups(level, conn=conn)
        coldefs = await self.make_coldefs(level, conn=conn)
        if not coldefs:
            return
        await self.make_columns_colnos_colnamestodisplay_columngroup(level, coldefs)
        if not self.nogenelevelonvariantlevel and self.level == "variant":
            await self.add_gene_level_columns_to_variant_level(conn)
        if self.level == "gene" and level == "gene" and add_summary:
            await self.exec_db(self.add_gene_level_summary_columns, level)
        self.set_display_select_columns(level)
        self.set_cols_to_display(level)
        #await self.place_priority_col_groups_first(level)
        #await self.order_columns_to_match_col_groups(level)
        self.colinfo[level] = {"colgroups": self.columngroups[level], "columns": self.columns[level]}
        await self.make_report_sub(level, conn)

    def get_standardized_module_option(self, v):
        tv = type(v)
        if tv == str:
            if ":" in v:
                v0 = {}
                for v1 in v.split("."):
                    if ":" in v1:
                        v1toks = v1.split(":")
                        if len(v1toks) == 2:
                            level = v1toks[0]
                            v2s = v1toks[1].split(",")
                            v0[level] = v2s
                v = v0
            elif "," in v:
                v = [val for val in v.split(",") if val != ""]
        if v == "true":
            v = True
        elif v == "false":
            v = False
        return v

    async def set_dbpath(self, dbpath=None):
        from os.path import exists
        from ..exceptions import NoInput
        from ..exceptions import WrongInput

        if dbpath != None:
            self.dbpath = dbpath
        if not self.dbpath:
            raise NoInput()
        if not exists(self.dbpath):
            raise WrongInput()

    async def close_db(self):
        import sqlite3
        for conn in self.conns:
            if type(conn) == sqlite3.Connection:
                conn.close()
            else:
                await conn.close()
        self.conns = []
        if self.cf is not None:
            await self.cf.close_db()
            self.cf = None

    async def load_filter(self, user=DEFAULT_SERVER_DEFAULT_USERNAME):
        from ..exceptions import SetupError
        from .. import ReportFilter

        if self.args is None:
            raise SetupError()
        self.cf = await ReportFilter.create(dbpath=self.dbpath, user=user, strict=False)
        await self.cf.exec_db(
            self.cf.loadfilter,
            filter=self.filter,
            filterpath=self.filterpath,
            filtername=self.filtername,
            filterstring=self.filterstring,
            filtersql=self.filtersql,
            includesample=self.args.get("includesample"),
            excludesample=self.args.get("excludesample"),
        )

    async def table_exists(self, tablename, conn=None, cursor=None):
        if conn is None:
            pass
        if cursor is None:
            from ..exceptions import SetupError

            raise SetupError()
        sql = (
            "select name from sqlite_master where "
            + 'type="table" and name="'
            + tablename
            + '"'
        )
        await cursor.execute(sql)
        row = await cursor.fetchone()
        if row == None:
            ret = False
        else:
            ret = True
        return ret


@cli_entry
def cli_report(args):
    return report(args)


@cli_func
def report(args, __name__="report"):
    from os.path import dirname
    from os.path import basename
    from os.path import join
    from asyncio import get_event_loop
    from ..util.util import is_compatible_version
    from importlib.util import spec_from_file_location
    from importlib.util import module_from_spec
    from ..exceptions import ModuleNotExist
    from ..exceptions import IncompatibleResult
    from ..util.util import quiet_print
    from ..module.local import get_local_module_info
    from ..system import consts
    from ..__main__ import handle_exception

    dbpath = args.get("dbpath")
    compatible_version, _, _ = is_compatible_version(dbpath)
    if not compatible_version:
        raise IncompatibleResult()
    report_types = args.get("reports")
    md = args.get("md")
    if md:
        consts.custom_modules_dir = md
    package = args.get("package")
    if not report_types:
        if package:
            m_info = get_local_module_info(package)
            if m_info:
                package_conf = m_info.conf
                if "run" in package_conf and "reports" in package_conf["run"]:
                    report_types = package_conf["run"]["reports"]
    output_dir = args.get("output_dir")
    if not output_dir:
        output_dir = dirname(dbpath)
    savepath = args.get("savepath")
    if not savepath:
        run_name = basename(dbpath).rstrip("sqlite").rstrip(".")
        args["savepath"] = join(output_dir, run_name)
    else:
        savedir = dirname(savepath)
        if savedir != "":
            output_dir = savedir
    module_options = {}
    module_option = args.get("module_option")
    if module_option:
        for opt_str in module_option:
            toks = opt_str.split("=")
            if len(toks) != 2:
                quiet_print(
                    "Ignoring invalid module option {opt_str}. module-option should be module_name.key=value.",
                    args,
                )
                continue
            k = toks[0]
            if k.count(".") != 1:
                quiet_print(
                    "Ignoring invalid module option {opt_str}. module-option should be module_name.key=value.",
                    args,
                )
                continue
            [module_name, key] = k.split(".")
            if module_name not in module_options:
                module_options[module_name] = {}
            v = toks[1]
            module_options[module_name][key] = v
    loop = get_event_loop()
    response = {}
    module_names = [v + "reporter" for v in report_types]
    for report_type, module_name in zip(report_types, module_names):
        try:
            module_info = get_local_module_info(module_name)
            if module_info is None:
                raise ModuleNotExist(report_type + "reporter")
            quiet_print(f"Generating {report_type} report... ", args)
            module_name = module_info.name
            spec = spec_from_file_location(  # type: ignore
                module_name, module_info.script_path  # type: ignore
            )
            if not spec:
                continue
            module = module_from_spec(spec)  # type: ignore
            if not module or not spec.loader:
                continue
            spec.loader.exec_module(module)
            args["module_name"] = module_name
            args["do_not_change_status"] = True
            if module_name in module_options:
                args["conf"] = module_options[module_name]
            reporter = module.Reporter(args)
            response_t = None
            response_t = loop.run_until_complete(reporter.run())
            output_fns = None
            if type(response_t) == list:
                output_fns = " ".join(response_t)
            else:
                output_fns = response_t
            if output_fns is not None and type(output_fns) == str:
                quiet_print(f"report created: {output_fns}", args)
            response[report_type] = response_t
        except Exception as e:
            handle_exception(e)
    return response


def cravat_report_entrypoint():
    args = get_parser_fn_report().parse_args(sys.argv[1:])
    cli_report(args)


def get_parser_fn_report():
    from argparse import ArgumentParser, SUPPRESS

    parser_ov_report = ArgumentParser(
        prog="ov report dbpath ...",
        description="Generate reports from result SQLite files",
        epilog="dbpath must be the first argument.",
    )
    parser_ov_report.add_argument("dbpath", help="Path to aggregator output")
    parser_ov_report.add_argument(
        "-t",
        dest="reports",
        nargs="+",
        default=[],
        help="report types",
    )
    parser_ov_report.add_argument(
        "-f", dest="filterpath", default=None, help="Path to filter file"
    )
    parser_ov_report.add_argument("--filter", default=None, help=SUPPRESS)
    parser_ov_report.add_argument("--filtersql", default=None, help="Filter SQL")
    parser_ov_report.add_argument(
        "-F",
        dest="filtername",
        default=None,
        help="Name of filter (stored in aggregator output)",
    )
    parser_ov_report.add_argument(
        "--filterstring", dest="filterstring", default=None, help=SUPPRESS
    )
    parser_ov_report.add_argument(
        "-s", dest="savepath", default=None, help="Path to save file"
    )
    parser_ov_report.add_argument("-c", dest="confpath", help="path to a conf file")
    parser_ov_report.add_argument(
        "--module-name", dest="module_name", default=None, help="report module name"
    )
    parser_ov_report.add_argument(
        "--nogenelevelonvariantlevel",
        dest="nogenelevelonvariantlevel",
        action="store_true",
        default=False,
        help="Use this option to prevent gene level result from being added to variant level result.",
    )
    parser_ov_report.add_argument(
        "--confs", dest="confs", default="{}", help="Configuration string"
    )
    parser_ov_report.add_argument(
        "--inputfiles",
        nargs="+",
        dest="inputfiles",
        default=None,
        help="Original input file path",
    )
    parser_ov_report.add_argument(
        "--separatesample",
        dest="separatesample",
        action="store_true",
        default=False,
        help="Write each variant-sample pair on a separate line",
    )
    parser_ov_report.add_argument(
        "-d", dest="output_dir", default=None, help="directory for output files"
    )
    parser_ov_report.add_argument(
        "--do-not-change-status",
        dest="do_not_change_status",
        action="store_true",
        default=False,
        help="Job status in status.json will not be changed",
    )
    parser_ov_report.add_argument(
        "--quiet",
        action="store_true",
        default=None,
        help="Suppress output to STDOUT",
    )
    parser_ov_report.add_argument(
        "--system-option",
        dest="system_option",
        nargs="*",
        help="System option in key=value syntax. For example, --system-option modules_dir=/home/user/oakvar/modules",
    )
    parser_ov_report.add_argument(
        "--module-option",
        dest="module_option",
        nargs="*",
        help="Module-specific option in module_name.key=value syntax. For example, --module-option vcfreporter.type=separate",
    )
    parser_ov_report.add_argument(
        "--concise-report",
        dest="concise_report",
        action="store_true",
        default=False,
        help="Generate concise report with default columns defined by annotation modules",
    )
    parser_ov_report.add_argument(
        "--includesample",
        dest="includesample",
        nargs="+",
        default=None,
        help="Sample IDs to include",
    )
    parser_ov_report.add_argument(
        "--excludesample",
        dest="excludesample",
        nargs="+",
        default=None,
        help="Sample IDs to exclude",
    )
    parser_ov_report.add_argument(
        "--package", help="Use filters and report types in a package"
    )
    parser_ov_report.add_argument(
        "--md",
        default=None,
        help="Specify the root directory of OakVar modules (annotators, etc)",
    )
    parser_ov_report.add_argument(
        "--cols",
        dest="cols",
        nargs="+",
        default=None,
        help="columns to include in reports",
    )
    parser_ov_report.add_argument(
        "--level",
        default=None,
        help="Level to make a report for. 'all' to include all levels. Other possible levels include 'variant' and 'gene'.",
    )
    parser_ov_report.add_argument(
        "--user",
        default=DEFAULT_SERVER_DEFAULT_USERNAME,
        help=f"User who is creating this report. Default is {DEFAULT_SERVER_DEFAULT_USERNAME}."
    )
    parser_ov_report.add_argument(
        "--no-summary",
        action="store_true",
        default=False,
        help="Skip gene level summarization. This saves time."
    )
    parser_ov_report.set_defaults(func=cli_report)
    return parser_ov_report

CravatReport = BaseReporter
