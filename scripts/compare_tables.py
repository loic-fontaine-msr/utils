import os
import click
from sqlalchemy import create_engine

import logging

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s", filename='logs/compare_table.log', filemode='w')

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(message)s'))

logger = logging.getLogger('CompareTable')
logger.addHandler(console_handler)

COMPARE_STRUCTURE = """ CREATE OR REPLACE TABLE {output_table} AS SELECT * FROM (
    SELECT
        COALESCE(A.COLUMN_NAME, B.COLUMN_NAME) AS COLUMN_NAME, A.DATA_TYPE as A_DATA_TYPE, B.DATA_TYPE as B_DATA_TYPE
    FROM
    (
        SELECT COLUMN_NAME, DATA_TYPE
        FROM {database_a}.INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = '{table_a}' AND TABLE_SCHEMA = '{schema_a}' AND COLUMN_NAME IN ({in_columns})
    ) A
    FULL OUTER JOIN
    (
        SELECT COLUMN_NAME, DATA_TYPE 
        FROM {database_b}.INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = '{table_b}' AND TABLE_SCHEMA = '{schema_b}' AND COLUMN_NAME IN ({in_columns})
    ) B ON A.COLUMN_NAME = B.COLUMN_NAME
    WHERE A.DATA_TYPE IS DISTINCT FROM B.DATA_TYPE
)"""

CHECK_STRUCTURE = """SELECT count(*) FROM {table_a}_structure_diff"""

MISSING_RECORDS = """ CREATE OR REPLACE TABLE {output_table} AS SELECT * FROM (
    SELECT {pk_cols_b}
    FROM (SELECT {pk_cols_b}, {table_b_update_ts} as last_update_ts FROM {full_table_b} b WHERE {table_b_filter}) b 
    LEFT OUTER JOIN (SELECT {pk_cols_a}, {table_a_update_ts} as last_update_ts FROM {full_table_a} a WHERE {table_a_filter}) a ON {pk_join_condition}
    WHERE {a_pk_empty_condition} AND greatest(a.last_update_ts, b.last_update_ts) < '{max_last_update_ts}'
)"""

ADDITIONAL_RECORDS = """ CREATE OR REPLACE TABLE {output_table} AS SELECT * FROM (
    SELECT {pk_cols_a}
    FROM (SELECT {pk_cols_a}, {table_a_update_ts} as last_update_ts FROM {full_table_a} a WHERE {table_a_filter}) a 
    LEFT OUTER JOIN (SELECT {pk_cols_b}, {table_b_update_ts} as last_update_ts FROM {full_table_b} b WHERE {table_b_filter}) b ON {pk_join_condition}    
    WHERE {b_pk_empty_condition} AND greatest(a.last_update_ts, b.last_update_ts) < '{max_last_update_ts}'
)"""

COMPARE_COLUMN_VALUES = """ CREATE OR REPLACE TABLE {output_table} AS SELECT * FROM (
    SELECT {pk_cols_a}, a.{column} AS a_{column}, b.{column} AS b_{column}
    FROM 
        (SELECT {pk_cols_a}, {transformed_column} as {column}, {table_a_update_ts} as last_update_ts FROM {full_table_a} a WHERE {table_a_filter}) a
    JOIN 
        (SELECT {pk_cols_b}, {transformed_column} as {column}, {table_b_update_ts} as last_update_ts FROM {full_table_b} b WHERE {table_b_filter}) b 
    ON {pk_join_condition}
    -- casting to string for comparison to workaround the float comparison issue. The structure of the table is compared separately.
    WHERE a.{column} IS DISTINCT FROM b.{column} AND greatest(a.last_update_ts, b.last_update_ts) < '{max_last_update_ts}'
)"""

@click.command()
@click.option('--connection-string', required=False, help='SQLAlchemy connection string', default=os.environ.get('COMPARE_CONNECTION_STRING'))
@click.option('--database-a', required=False, help='Database A name', default=os.environ.get('COMPARE_DATABASE_A'))
@click.option('--database-b', required=False, help='Database B name', default=os.environ.get('COMPARE_DATABASE_B'))
@click.option('--schema-a', required=False, help='Schema A name', default=os.environ.get('COMPARE_SCHEMA_A'))
@click.option('--schema-b', required=False, help='Schema B name', default=os.environ.get('COMPARE_SCHEMA_B'))
@click.option('--table-a', required=True, help='Table A name')
@click.option('--table-a-filter', help='Table A filter', default="1=1")
@click.option('--table-a-update-ts', required=True, help='Table A last update timestamp')
@click.option('--table-b', required=True, help='Table B name')
@click.option('--table-b-filter', help='Table B filter', default="1=1")
@click.option('--table-b-update-ts', required=True, help='Table B last update timestamp')
@click.option('--pks', required=False, help='commat separated list of pk columns', default="ID")
@click.option('--columns', required=False, help='commat separated list of columns to compares')
@click.option('--exclude-columns', required=False, help='commat separated list of columns to exclude from comparison', default="")
@click.option('--diff-target-schema', required=False, help='Target schema name', default=os.environ.get('COMPARE_TARGET_SCHEMA'))
@click.option('--max-last-update-ts', required=True, help='Max last update TS')
def compare_tables(
        connection_string: str, 
        database_a: str, schema_a: str, table_a: str, table_a_filter: str, table_a_update_ts: str,
        database_b: str, schema_b: str, table_b: str, table_b_filter: str, table_b_update_ts: str,
        pks: str, columns: str, exclude_columns: str,
        diff_target_schema: str,
        max_last_update_ts: str
    ):

    pks = pks.split(',')
    columns = columns.split(',') if columns else []
    exclude_columns = exclude_columns.split(',') if exclude_columns else []

    engine = create_engine(connection_string)
    column_rows = engine.execute(f"DESCRIBE TABLE {database_a}.{schema_a}.{table_a}").fetchall()
    columns = [c['name'] for c in column_rows if not c['name'].startswith('_') and c['name'] not in pks and c['name'] not in exclude_columns] if not columns else columns
    columns_type = {c['name']:c['type'] for c in column_rows}

    params = {
        'full_table_a': f"{database_a}.{schema_a}.{table_a}", 'database_a': database_a, 'schema_a': schema_a, 'table_a': table_a,
        'full_table_b': f"{database_b}.{schema_b}.{table_b}", 'database_b': database_b, 'schema_b': schema_b, 'table_b': table_b,
        'diff_target_schema': diff_target_schema,
        'pk_join_condition': ' AND '.join([f'a.{p} = b.{p}' for p in pks]),
        'a_pk_empty_condition': ' AND '.join([f'a.{p} IS NULL' for p in pks]),
        'b_pk_empty_condition': ' AND '.join([f'b.{p} IS NULL' for p in pks]),
        'pk_cols_a': ', '.join([f'a.{p}' for p in pks]),
        'pk_cols_b': ', '.join([f'b.{p}' for p in pks]),
        'columns_a': ', '.join([f'a.{c}' for c in columns]),
        'columns_b': ', '.join([f'b.{c}' for c in columns]),
        'columns_a_renamed': ', '.join([f'a.{c} as a_{c}' for c in columns]),
        'columns_b_renamed': ', '.join([f'b.{c} as b_{c}' for c in columns]),
        'in_columns': ', '.join([f'\'{c.upper()}\'' for c in columns]),
        'table_a_filter': table_a_filter,
        'table_b_filter': table_b_filter,
        'table_a_update_ts': table_a_update_ts,
        'table_b_update_ts': table_b_update_ts,
        'max_last_update_ts': max_last_update_ts
    }

    logger.info(f"Comparing tables {params['full_table_a']} (A) & {params['full_table_b']} (B):")
    logger.debug("Input parameters {params}")

    def compare(sql: str, msg: str):
        logger.info(f"  Checking for {msg}...")

        output_table = f"{table_a}_{msg.replace(' ', '_')}"
        params['output_table'] = output_table
        
        sql_query = sql.format(**params)
        logger.debug(f"Running SQL: {sql_query}")
        engine.execute(sql_query)
        mismatches = engine.execute(f"SELECT count(*) FROM {output_table}".format(**params)).fetchone()[0]

        if mismatches:
            logger.info(f"  {msg} ❌: {mismatches} mismatches")
        else:
            logger.info(f"  No {msg} ✅")

        return mismatches == 0

    engine.execute(f"CREATE SCHEMA IF NOT EXISTS {diff_target_schema};")
    engine.execute(f"USE SCHEMA {diff_target_schema};")
    
    check = compare(COMPARE_STRUCTURE, 'structures mismatches')
    check = compare(MISSING_RECORDS, 'records missing') and check
    check = compare(ADDITIONAL_RECORDS, 'additional records') and check
    for column in columns:
        params['column'] = column
        params['transformed_column'] = f"ROUND({column})" if (columns_type[column].startswith('FLOAT')) else f"CAST({column} AS STRING)"
        check = compare(COMPARE_COLUMN_VALUES, f"mismatches on column {column}") and check

    logger.info(f"Tables {params['full_table_a']} (A) & {params['full_table_b']} are {'similar ✅' if check else f'different ❌. Checkout the mismatches details in the schema {diff_target_schema}'}")
    exit(0 if check else 1)

if __name__ == "__main__":
    compare_tables()
