import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const { name, gamesText } = await request.json();

    if (!name || !gamesText) {
      return NextResponse.json({ error: 'Name and gamesText are required' }, { status: 400 });
    }

    const rommUrl = process.env.ROMM_URL?.replace(/\/$/, '');
    const apiKey = process.env.ROMM_API_KEY;

    if (!rommUrl || !apiKey) {
      return NextResponse.json({ error: 'Server configuration error: ROMM_URL or ROMM_API_KEY missing' }, { status: 500 });
    }

    const headers = {
      'Authorization': `Bearer ${apiKey}`
    };

    // 1. Fetch all ROMs
    let allRoms: any[] = [];
    let offset = 0;
    const limit = 1000;
    let hasMore = true;

    while (hasMore) {
      const res = await fetch(`${rommUrl}/api/roms?limit=${limit}&offset=${offset}`, { headers });
      if (!res.ok) {
        throw new Error(`Failed to fetch ROMs: ${res.statusText}`);
      }
      const data = await res.json();
      if (data.items && data.items.length > 0) {
        allRoms = allRoms.concat(data.items);
        offset += limit;
      } else {
        hasMore = false;
      }
      if (!data.items || data.items.length < limit) {
        hasMore = false;
      }
    }

    // 2. Fuzzy match games
    const games = gamesText.split('\n').map((g: string) => g.trim()).filter((g: string) => g.length > 0);
    const addedGames: string[] = [];
    const missingGames: string[] = [];
    const romIdsToAdd: number[] = [];

    const normalize = (str: string) => str.toLowerCase().replace(/[^a-z0-9]/g, '');

    for (const game of games) {
      // Remove platform hints from parentheses if they exist at the end, e.g. "Adventure (Atari 2600)" -> "Adventure"
      const cleanGameName = game.replace(/\s*\(.*?\)$/, '').trim();
      const normGame = normalize(cleanGameName);
      
      const match = allRoms.find(rom => {
        const normRomName = normalize(rom.name || '');
        return normRomName === normGame || normRomName.includes(normGame) || normGame.includes(normRomName);
      });

      if (match) {
        romIdsToAdd.push(match.id);
        addedGames.push(game); // Keep original formatting for results
      } else {
        missingGames.push(game);
      }
    }

    // 3. Create Collection
    // RomM expects multipart/form-data for collection creation
    const formData = new FormData();
    formData.append('name', name);
    formData.append('description', 'Created via RomM Collection Creator');

    const createRes = await fetch(`${rommUrl}/api/collections`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`
        // Do not set Content-Type, fetch will automatically set it with the boundary
      },
      body: formData
    });

    if (!createRes.ok) {
      const err = await createRes.text();
      return NextResponse.json({ error: `Failed to create collection: ${err}` }, { status: createRes.status });
    }

    const collection = await createRes.json();
    const collectionId = collection.id;

    // 4. Add ROMs to Collection
    if (romIdsToAdd.length > 0) {
      const updateParams = new URLSearchParams();
      updateParams.append('name', name);
      updateParams.append('description', 'Created via RomM Collection Creator');
      updateParams.append('rom_ids', JSON.stringify(Array.from(new Set(romIdsToAdd))));

      const addRomsRes = await fetch(`${rommUrl}/api/collections/${collectionId}?is_public=false`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: updateParams.toString()
      });

      if (!addRomsRes.ok) {
        const err = await addRomsRes.text();
        return NextResponse.json({ error: `Collection created but failed to add ROMs: ${err}` }, { status: addRomsRes.status });
      }
    }

    return NextResponse.json({
      success: true,
      addedGames,
      missingGames,
      collectionId
    });

  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Internal Server Error' }, { status: 500 });
  }
}
