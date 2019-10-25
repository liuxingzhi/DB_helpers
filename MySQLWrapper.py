# coding=utf8
from __future__ import annotations
from typing import Dict, List, Optional, Union, Tuple, TypeVar, Sequence
import mysql.connector
from DBUtils.PooledDB import PooledDB, PooledDedicatedDBConnection, PooledSharedDBConnection
from tabulate import tabulate
import pandas as pd
from collections import OrderedDict
import logging

logging.basicConfig(level=logging.INFO)


class MySQLWrapper:
    __pool = None

    def __init__(self, db_name="testing") -> None:
        self._connection = MySQLWrapper.get_conn(db_name)
        self.cursor = self._connection.cursor()

        # # 立即将本次数据库连接设成utf-8编码
        # self._connection.set_character_set('utf8')
        # self.cursor.execute('SET NAMES utf8;')
        # self.cursor.execute('SET CHARACTER SET utf8;')
        # self.cursor.execute('SET character_set_connection=utf8;')

    @staticmethod
    def get_conn(db_name="testing", user="username", password="password", host="localhost", port=3306) -> Union[
        PooledSharedDBConnection, PooledDedicatedDBConnection]:
        """
        静态方法，从连接池中取出连接
        return sqlite.connection
        """
        if MySQLWrapper.__pool is None:
            MySQLWrapper.__pool = PooledDB(creator=mysql.connector, mincached=1, maxcached=5, host=host, port=port,
                                           user=user,
                                           password=password, database=db_name, charset='utf8')
        return MySQLWrapper.__pool.connection()

    def create_table_by_datadict(self, table_name: str, str_data_dict: Dict) -> None:
        """will create all fields as text field"""
        fields = " text,\n".join([str(x) for x in str_data_dict.keys()])
        sql = f"""create table if not exists {table_name}(
        {fields} text);"""
        self.create_table(sql, table_name)

    def query_table_columns(self, table_name: str) -> List[str]:
        """same as quert title"""
        sql = f"select * from {table_name} limit 0"
        return self.query_title(sql)

    def query_all_return_json(self, sql: str, params: Optional[Sequence] = None) -> List[OrderedDict]:
        datalist = []
        result = self.query_all(sql, params)
        for row in result:
            one_row_dict = OrderedDict()
            for description_tuple, value in zip(self.cursor.description, row):
                one_row_dict[description_tuple[0]] = value
            datalist.append(one_row_dict)
        return datalist

    def query_all_return_pandas(self, sql: str, params: Optional[Sequence] = None) -> pd.DataFrame:
        datalist = self.query_all_return_json(sql, params)
        return pd.DataFrame(datalist)

    def query_all_dumps2excel(self, sql: str, params: Optional[Sequence] = None, dumped_excel="dumped.xlsx") -> None:
        pd = self.query_all_return_pandas(sql, params)
        pd.to_excel(dumped_excel)

    def table2excel(self, table_name: str, dumped_excel: Optional[str] = None) -> None:
        sql = f"select * from {table_name}"
        if dumped_excel:
            self.query_all_dumps2excel(sql, dumped_excel=dumped_excel)
        else:
            self.query_all_dumps2excel(sql, dumped_excel=(table_name + ".xlsx"))

    def table2pandas(self, table_name: str) -> pd.DataFrame:
        sql = f"select * from {table_name}"
        return self.query_all_return_pandas(sql)

    def table2json(self, table_name: str) -> List[OrderedDict]:
        sql = f"select * from {table_name}"
        return self.query_all_return_json(sql)

    def query_all_tabulated(self, sql: str, params: Optional[Sequence] = None) -> str:
        data_df = self.query_all_return_pandas(sql, params)
        prettified = tabulate(data_df, headers=data_df.columns, tablefmt='fancy_grid')
        if prettified == "":
            prettified = "No Result"
        print(prettified)
        return prettified

    def query_title(self, sql: str, params: Optional[Sequence] = None) -> List[str]:
        """return table headers"""
        if "limit" not in sql:
            sql += " limit 0"
        if len(params) > 0:
            self.cursor.execute(sql, params)
        else:
            self.cursor.execute(sql)
        col_names = []
        # print(self.cursor.description)
        for info in self.cursor.description:
            col_names.append(info[0])
        return col_names

    def query_all(self, sql: str, params: Optional[Sequence] = None) -> List[Tuple]:
        """select all matched query result"""
        if params:
            self.cursor.execute(sql, params)
        else:
            self.cursor.execute(sql)
        return self.cursor.fetchall()

    def query_one(self, sql: str, params: Optional[Sequence] = None) -> Tuple:
        """select one matched query result"""
        if params:
            self.cursor.execute(sql, params)
        else:
            self.cursor.execute(sql)
        return self.cursor.fetchone()

    def insert_one_row_by_dict(self, table_name: str, data_dict: Dict, force: bool = False) -> None:
        """insert a json format dictionary"""
        sql_pre = "insert into {table} (%s) values (%s)".format(table=table_name)
        if force:
            sql_pre = "replace into {table} (%s) values (%s)".format(table=table_name)
        # clean the dict
        fields = data_dict.keys()
        bindvars = ["%(" + x + ")s" for x in data_dict.keys()]
        bindvars = ",".join(bindvars)
        sql = sql_pre % (",".join(fields), bindvars)
        # print(sql)
        # print(data_dict)
        # try:
        self.insert_one(sql, data_dict)
        # except MySQLdb.IntegrityError as e:  # 如果有重复，就跳过它
        #     logging.log(e)
        # print("data duplicate:", data_dict)

    def insert_one(self, sql: str, params: Optional[Sequence] = None) -> None:
        # print(sql)
        if params is None:
            self.cursor.execute(sql)
        else:
            self.cursor.execute(sql, params)
        self.commit()

    def upper_all(self, table_name: str) -> None:
        """uppercase whole table"""
        columns = self.query_title(f"select * from {table_name}")
        for column in columns:
            print(column)
            sql = f"update {table_name} set {column} = upper({column})"
            # print(sql)
            self.cursor.execute(sql)
            self.commit()

    def lower_all(self, table_name: str) -> None:
        """lowercase whole table"""
        columns = self.query_title(f"select * from {table_name}")
        for column in columns:
            print(column)
            sql = f"update {table_name} set {column} = lower({column})"
            print(sql)
            self.cursor.execute(sql)
            self.commit()

    def insert_batch_from_dataframe(self, result_df: pd.DataFrame, table_name: str) -> None:
        """batch insert from pandas dataframe"""
        values = []
        for index, row in result_df.iterrows():
            values.append(tuple(row))

        cols_str = ",".join((tuple(result_df.columns)))
        num_list_str = ""
        for i in range(1, len(result_df.columns) + 1):
            num_list_str += "%s,"
        num_list_str = num_list_str[:-1]

        sql = f"INSERT INTO {table_name}({cols_str}) VALUES({num_list_str})"
        # print(sql)
        self.insert_batch(sql, values)

    def insert_batch(self, sql: str, value_list: List) -> None:
        self.cursor.executemany(sql, value_list)
        self.commit()

    def delete_from(self, table_name: str, conditions: str) -> None:
        sql = f"delete from {table_name} where {conditions}"
        self.cursor.execute(sql)
        self.commit()
        print(f"executed sql: {sql}")

    def erase_table(self, table_name: str) -> None:
        """clear a whole table"""
        sql = "delete from " + table_name
        print(f"started to erase {table_name}")
        self.cursor.execute(sql)
        self.commit()
        print(f"data in {table_name} has been cleared")

    def backup(self, table: str) -> None:
        """backup a table"""
        sql = f"create table {table.upper() + '_BACK_UP'} as select * from {table}"
        """直接建表不用commit"""
        # print(sql)
        try:
            self.cursor.execute(sql)
        except MySQLdb.OperationalError:
            self.cursor.execute(f"drop table {table.upper() + '_BACK_UP'}")
            self.cursor.execute(sql)

    def recover_from(self, table_recovered: str, backup: str) -> None:
        """recover a table"""
        self.copy_table(backup, table_recovered)

    def recover_from_backup(self, table: str) -> None:
        """recover a table from back_up table"""
        self.recover_from(table, f"{table.upper() + '_BACK_UP'}")

    def copy_table(self, table_origin: str, table_dest: str) -> None:
        """copy a table into a new table"""
        self.erase_table(table_dest)
        sql = f"insert into {table_dest} select * from {table_origin}"
        # print(sql)
        self.cursor.execute(sql)
        self.commit()

    def create_table(self, sql: str) -> None:
        self.cursor.execute(sql)
        # print(sql)
        self.commit()

    def commit(self) -> None:
        self._connection.commit()

    def release(self) -> None:
        if hasattr(self, 'cursor') and self.cursor:
            self.cursor.close()
            self.cursor = None
            print("Released cursor")
        if hasattr(self, '_connection') and self._connection:
            self._connection.close()
            self._connection = None
            print("Released connection")

    def execute(self, sql: str, params=None, multi=False) -> None:
        if multi:
            for result in self.cursor.execute(sql, multi=True):
                if result.with_rows:
                    print("Rows produced by statement '{}':".format(
                        result.statement))
                    print(result.fetchall())
                else:
                    print("Number of rows affected by statement '{}': {}".format(
                        result.statement, result.rowcount))
        else:
            self.cursor.execute(sql, params, multi=multi)

    def fetchall(self) -> List[Tuple]:
        return self.cursor.fetchall()

    def __enter__(self) -> MySQLWrapper:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
        # print(exc_type,exc_val,exc_tb)

    def __del__(self):
        self.release()


if __name__ == '__main__':
    job_title = "manager"
    location = "IL"
    company_name = ""
    industry = "Internet"

    with MySQLWrapper() as db:
        sql = """ 
                   DROP TABLE IF EXISTS MYTEST;
                   CREATE TABLE IF NOT EXISTS MYTEST(
                   ID INT PRIMARY KEY,
                   CONTENT TEXT
                   );
                   INSERT INTO MYTEST(ID, CONTENT) VALUES (1, "TESTING");
                   SELECT * FROM MYTEST;"""
        r = db.execute(sql, multi=True)
        db.commit()
        print(r)
        # sql = f'''select * from job as j
        #    inner join company as c
        #    on c.company_id = j.company_id
        #    where lower(j.job_title) like "%{job_title}%"
        #    and j.location like BINARY "%{location}%"
        #    and c.company_name like "%{company_name}%"
        #    and c.industry like "%{industry}%"
        #    order by j.job_id, j.location, c.industry, c.company_id asc'''
        # sql = """
        # CREATE TABLE IF NOT EXISTS FRUITS_PROMOTION(
        #     AREA VARCHAR(10),
        #     GENRE VARCHAR(1),
        #     ITEM_CODE INTEGER,
        #     CODE_LENGTH INTEGER,
        #     FROM_DATE DATETIME,
        #     END_DATE DATETIME,
        #     FROM_FILENAME VARCHAR(50),
        #     FIRST_4 BOOLEAN DEFAULT FALSE,
        #     LAST_3 BOOLEAN DEFAULT FALSE,
        #     PARAGRAPH TEXT
        #     );
        # """
        # cursor.execute(sql)
        # results = cursor.fetchall()
        # for r in results:
        #     print(r)
