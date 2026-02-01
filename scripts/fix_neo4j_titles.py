import asyncio
import sys
import os

# Adjust path
sys.path.append(os.getcwd())

from app.core.neo4j_client import neo4j_client

# [UTF-8]
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

async def fix_titles():
    print("=== Neo4j Null Title Fixer ===")
    
    async with neo4j_client.driver.session() as session:
        # 1. Find nodes with issues
        find_query = """
        MATCH (n)
        WHERE (n.title IS NULL OR n.title = 'None' OR n.title = '') 
          AND labels(n)[0] IN ['Concept', 'Requirement', 'Decision', 'Task']
        RETURN count(n) as cnt
        """
        result = await session.run(find_query)
        record = await result.single()
        count = record["cnt"]
        print(f"Found {count} nodes with missing titles.")
        
        if count == 0:
            return

        # 2. Fix them
        # Logic: 
        # - Use 'name' property if exists
        # - Else use first 20 chars of 'content'
        # - Else 'Untitled Node'
        fix_query = """
        MATCH (n)
        WHERE (n.title IS NULL OR n.title = 'None' OR n.title = '') 
          AND labels(n)[0] IN ['Concept', 'Requirement', 'Decision', 'Task']
        SET n.title = COALESCE(n.name, substring(n.content, 0, 30) + '...', 'Untitled ' + labels(n)[0])
        RETURN count(n) as fixed_cnt
        """
        print("Applying fixes...")
        result = await session.run(fix_query)
        record = await result.single()
        print(f"✅ Fixed {record['fixed_cnt']} nodes.")

if __name__ == "__main__":
    asyncio.run(fix_titles())
