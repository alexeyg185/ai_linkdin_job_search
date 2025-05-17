from app import logger
from database.db_manager import DatabaseManager
from database.models import JobStates


def clear_stale_queued_jobs():
    """
    Clean up jobs that are stuck in the queued_for_analysis state even though
    they have already been processed (have a newer analyzed, relevant, or irrelevant state).

    Returns:
        int: Number of stale queue entries removed
    """
    db_manager = DatabaseManager()

    query = f"""
    DELETE FROM {JobStates.TABLE_NAME} 
    WHERE state = '{JobStates.STATE_QUEUED_FOR_ANALYSIS}'
    AND EXISTS (
        SELECT 1
        FROM {JobStates.TABLE_NAME} newer
        WHERE newer.job_id = {JobStates.TABLE_NAME}.job_id 
        AND newer.user_id = {JobStates.TABLE_NAME}.user_id
        AND newer.state IN ('{JobStates.STATE_ANALYZED}', '{JobStates.STATE_RELEVANT}', '{JobStates.STATE_IRRELEVANT}')
        AND newer.state_timestamp > {JobStates.TABLE_NAME}.state_timestamp
    )
    """

    with db_manager.transaction() as conn:
        cursor = conn.execute(query)
        rows_affected = cursor.rowcount

    logger.info(f"Removed {rows_affected} stale queued jobs from the database")
    return rows_affected


if __name__ == "__main__":
    affected_rows = clear_stale_queued_jobs()
    print(f"Successfully removed {affected_rows} already analyzed jobs from the queue.")