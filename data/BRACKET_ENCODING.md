# Bracket Encoding Guide

Each bracket is stored as **5 packed integers** representing 63 total games.

## Regional Columns (15 bits each)

`east_outcomes`, `south_outcomes`, `west_outcomes`, `midwest_outcomes`

Each bit represents one game. **Bit = 0** means the higher seed (top team) won. **Bit = 1** means the lower seed (bottom team) won.

### Bit Layout

```
Bits 0-7:   Round of 64 (8 games)
Bits 8-11:  Round of 32 (4 games)
Bits 12-13: Sweet 16    (2 games)
Bit  14:    Elite 8     (1 game)
```

### R64 Game Mapping (Bits 0–7)

| Bit | Game | Top Team (bit=0 wins) | Bottom Team (bit=1 wins) |
|-----|------|-----------------------|--------------------------|
| 0 | 1v16 | 1-seed | 16-seed |
| 1 | 8v9 | 8-seed | 9-seed |
| 2 | 5v12 | 5-seed | 12-seed |
| 3 | 4v13 | 4-seed | 13-seed |
| 4 | 6v11 | 6-seed | 11-seed |
| 5 | 3v14 | 3-seed | 14-seed |
| 6 | 7v10 | 7-seed | 10-seed |
| 7 | 2v15 | 2-seed | 15-seed |

### R32 Game Mapping (Bits 8–11)

| Bit | Game | Top Team (bit=0 wins) | Bottom Team (bit=1 wins) |
|-----|------|-----------------------|--------------------------|
| 8 | R32 A | Winner of bit 0 (1/16) | Winner of bit 1 (8/9) |
| 9 | R32 B | Winner of bit 2 (5/12) | Winner of bit 3 (4/13) |
| 10 | R32 C | Winner of bit 4 (6/11) | Winner of bit 5 (3/14) |
| 11 | R32 D | Winner of bit 6 (7/10) | Winner of bit 7 (2/15) |

### Sweet 16 Game Mapping (Bits 12–13)

| Bit | Game | Top Team (bit=0 wins) | Bottom Team (bit=1 wins) |
|-----|------|-----------------------|--------------------------|
| 12 | S16 A | Winner of bit 8 | Winner of bit 9 |
| 13 | S16 B | Winner of bit 10 | Winner of bit 11 |

### Elite 8 (Bit 14)

| Bit | Game | Top Team (bit=0 wins) | Bottom Team (bit=1 wins) |
|-----|------|-----------------------|--------------------------|
| 14 | E8 | Winner of bit 12 | Winner of bit 13 |

**The winner of bit 14 is the regional champion.**

## Final Four Column (3 bits)

`f4_outcomes` — values 0 through 7.

| Bit | Game | Top Team (bit=0 wins) | Bottom Team (bit=1 wins) |
|-----|------|-----------------------|--------------------------|
| 0 | Semi 1 | East champion | South champion |
| 1 | Semi 2 | West champion | Midwest champion |
| 2 | Championship | Winner of Semi 1 | Winner of Semi 2 |

## Example

East outcome = `11794` → binary `10111000010010`

```
Bit 14 (E8):  1 → bottom team won (S16 B winner)
Bit 13 (S16B): 0 → top team won
Bit 12 (S16A): 1 → bottom team won
Bit 11 (R32D): 1 → bottom team won (2-seed lost)
Bit 10 (R32C): 1 → bottom team won
Bit 9  (R32B): 0 → top team won
Bit 8  (R32A): 0 → top team won (1-seed advanced)
Bit 7  (2v15): 0 → 2-seed won
Bit 6  (7v10): 1 → 10-seed won (UPSET)
Bit 5  (3v14): 0 → 3-seed won
Bit 4  (6v11): 0 → 6-seed won
Bit 3  (4v13): 1 → 13-seed won (UPSET)
Bit 2  (5v12): 0 → 5-seed won
Bit 1  (8v9):  1 → 9-seed won (UPSET)
Bit 0  (1v16): 0 → 1-seed won
```

## 2026 Teams by Region

### East
1-Duke, 2-UConn, 3-Michigan State, 4-Kansas, 5-St. John's, 6-Louisville, 7-UCLA, 8-Ohio State, 9-TCU, 10-UCF, 11-South Florida, 12-Northern Iowa, 13-Cal Baptist, 14-North Dakota State, 15-Furman, 16-Siena

### South
1-Florida, 2-Houston, 3-Illinois, 4-Nebraska, 5-Vanderbilt, 6-North Carolina, 7-Saint Mary's, 8-Clemson, 9-Iowa, 10-Texas A&M, 11-VCU, 12-McNeese, 13-Troy, 14-Penn, 15-Idaho, 16-Prairie View A&M

### West
1-Arizona, 2-Purdue, 3-Gonzaga, 4-Arkansas, 5-Wisconsin, 6-BYU, 7-Miami, 8-Villanova, 9-Utah State, 10-Missouri, 11-Texas, 12-High Point, 13-Hawaii, 14-Kennesaw State, 15-Queens, 16-LIU

### Midwest
1-Michigan, 2-Iowa State, 3-Virginia, 4-Alabama, 5-Texas Tech, 6-Tennessee, 7-Kentucky, 8-Georgia, 9-Saint Louis, 10-Santa Clara, 11-Miami (OH), 12-Akron, 13-Hofstra, 14-Wright State, 15-Tennessee State, 16-Howard
