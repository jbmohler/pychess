import re
import argparse
import termcolor


class ChessPiece:
    wk = "\u2654"
    wq = "\u2655"
    wr = "\u2656"
    wb = "\u2657"
    wn = "\u2658"
    wp = "\u2659"
    bk = "\u265a"
    bq = "\u265b"
    br = "\u265c"
    bb = "\u265d"
    bn = "\u265e"
    bp = "\u265f"
    empty = " "

    backfile = "rnbqkbnr"


class InterpretationError(Exception):
    pass


class Delta:
    f2i = {c: ord(c) - ord("a") for c in "abcdefgh"}
    r2i = {c: ord(c) - ord("1") for c in "12345678"}
    i2f = {i: chr(i + ord("a")) for i in range(8)}
    i2r = {i: chr(i + ord("1")) for i in range(8)}

    __slots__ = ["df", "dr"]

    def __init__(self, df, dr):
        self.df = df
        self.dr = dr

    def __mul__(self, mult):
        return Delta(self.df * mult, self.dr * mult)

    def __repr__(self):
        return f"Delta({self.df}, {self.dr})"

    def from_(self, spot):
        f, r = Delta.f2i[spot[0]], Delta.r2i[spot[1]]
        # assert 0 <= f < 8 and 0 <= r < 8
        f += self.df
        r += self.dr
        if 0 <= f < 8 and 0 <= r < 8:
            return f"{Delta.i2f[f]}{Delta.i2r[r]}"
        else:
            raise IndexError(f"{spot} offset ({self.df}, {self.dr}) is out of bounds")


class Board:
    CASTLE_SPOTS = ["a1", "e1", "h1", "a8", "e8", "h8"]

    def __init__(self, piecemap):
        self.piecemap = piecemap

        self.enpassant = None
        self.castle_x = set()
        self.history = []

    def _dupe(self):
        x = Board(self.piecemap.copy())
        x.enpassant = self.enpassant
        x.castle_x = self.castle_x.copy()
        x.history = self.history.copy()
        return x

    @staticmethod
    def default_board():
        cp = ChessPiece
        files = "abcdefgh"

        rank1 = {f"{f}1": f"w{p}" for f, p in zip(files, cp.backfile)}
        rank2 = {f"{f}2": "wp" for f in files}
        rank7 = {f"{f}7": "bp" for f in files}
        rank8 = {f"{f}8": f"b{p}" for f, p in zip(files, cp.backfile)}

        return Board({**rank1, **rank2, **rank7, **rank8})

    def __getitem__(self, spot):
        return self.piecemap.get(spot, "empty")

    def _positions(self, color):
        for k, v in self.piecemap.items():
            if v[0] == color:
                yield k, v

    def who(self):
        return {0: "w", 1: "b"}[len(self.history) % 2]

    @staticmethod
    def other(who):
        return {"w": "b", "b": "w"}[who]

    def is_attacked(self, spot, who):
        for check in self._positional_moves(who, attacking=spot):
            if check[1] == spot:
                return True
        return False

    def is_positional_check(self, who):
        king_spot = [s for s, p in self._positions(who) if p[1] == "k"][0]
        return self.is_attacked(king_spot, Board.other(who))

    def legal_moves(self):
        for candidate in self._positional_moves():
            plynow = {0: "w", 1: "b"}[len(self.history) % 2]

            # does making this move leave me in check?
            chboard = self.make_move(candidate, ignore_promote=True)
            if not chboard.is_positional_check(plynow):
                if self[candidate[0]][1] == "p" and candidate[1][1] in "18":
                    # pawn promotion
                    for promote in "qbnr":
                        yield (*candidate, promote)
                else:
                    yield candidate

    def _attacked_positions(self, who):
        d_straight = [Delta(0, 1), Delta(1, 0)]
        d_straight = [s for s in d_straight] + [s * -1 for s in d_straight]
        d_diag = [Delta(1, 1), Delta(1, -1)]
        d_diag = [s for s in d_diag] + [s * -1 for s in d_diag]
        d_knight = [Delta(2, 1), Delta(2, -1), Delta(1, 2), Delta(-1, 2)]
        d_knight = [s for s in d_knight] + [s * -1 for s in d_knight]

        for spot, piece in self._positions(who):
            if piece[1] == "p":
                dr = {"b": -1, "w": 1}[piece[0]]
                for df in (-1, 1):
                    try:
                        yield Delta(df, dr).from_(spot)
                    except IndexError:
                        continue
            else:
                dirs = {
                    "r": d_straight,
                    "b": d_diag,
                    "q": d_straight + d_diag,
                    "k": d_straight + d_diag,
                    "n": d_knight,
                }[piece[1]]
                distance = 2 if piece[1] in "kn" else 8
                for dd in dirs:
                    for i in range(1, distance):
                        offset = dd * i
                        try:
                            spot2 = offset.from_(spot)
                        except IndexError:
                            break
                        if self[spot2] == "empty":
                            yield spot2
                        elif self[spot2][0] == Board.other(who):
                            yield spot2
                            break
                        elif self[spot2][0] == who:
                            break
                        else:
                            raise RuntimeError("unexpected element")

    def _positional_moves(self, who=None, attacking=None):
        if who:
            plynow = who
            plyother = Board.other(who)
        else:
            plynow = {0: "w", 1: "b"}[len(self.history) % 2]
            plyother = {0: "b", 1: "w"}[len(self.history) % 2]

        d_straight = [Delta(0, 1), Delta(1, 0)]
        d_straight = [s for s in d_straight] + [s * -1 for s in d_straight]
        d_diag = [Delta(1, 1), Delta(1, -1)]
        d_diag = [s for s in d_diag] + [s * -1 for s in d_diag]
        d_knight = [Delta(2, 1), Delta(2, -1), Delta(1, 2), Delta(-1, 2)]
        d_knight = [s for s in d_knight] + [s * -1 for s in d_knight]

        for spot, piece in self._positions(plynow):
            if piece[1] == "p":
                dr = {"b": -1, "w": 1}[piece[0]]
                for df in (-1, 0, 1):
                    try:
                        spot2 = Delta(df, dr).from_(spot)
                    except IndexError:
                        continue
                    if df == 0:
                        if self[spot2] == "empty":
                            yield (spot, spot2)
                            if spot[1] == {"b": "7", "w": "2"}[piece[0]]:
                                try:
                                    spot2 = Delta(df, dr * 2).from_(spot)
                                except IndexError:
                                    continue
                                if self[spot2] == "empty":
                                    yield (spot, spot2)
                    else:
                        eptarget = None if not self.enpassant else self.enpassant[0]
                        if self[spot2][0] == plyother or spot2 == eptarget:
                            yield (spot, spot2)
            else:
                dirs = {
                    "r": d_straight,
                    "b": d_diag,
                    "q": d_straight + d_diag,
                    "k": d_straight + d_diag,
                    "n": d_knight,
                }[piece[1]]
                distance = 2 if piece[1] in "kn" else 8
                for dd in dirs:
                    for i in range(1, distance):
                        offset = dd * i
                        try:
                            spot2 = offset.from_(spot)
                        except IndexError:
                            break
                        if self[spot2] == "empty":
                            yield (spot, spot2)
                        elif self[spot2][0] == plyother:
                            yield (spot, spot2)
                            break
                        elif self[spot2][0] == plynow:
                            break
                        else:
                            raise RuntimeError("unexpected element")

                k_spot = {"w": "e1", "b": "e8"}[plynow]
                if (
                    piece[1] == "k"
                    and spot == k_spot
                    and spot not in self.castle_x
                    and (attacking == None or attacking[1] == k_spot[1])
                ):
                    # king side
                    d1 = Delta(1, 0)
                    lineup = [(d1 * i).from_(spot) for i in range(4)]
                    if (
                        self[lineup[-1]][1] == "r"
                        and lineup[-1] not in self.castle_x
                        and set([self[smid] for smid in lineup[1:-1]]) == {"empty"}
                    ):
                        if not any(
                            self.is_attacked(smid, plyother) for smid in lineup[:3]
                        ):
                            yield (spot, lineup[2])

                    # queen side
                    d1 = Delta(-1, 0)
                    lineup = [(d1 * i).from_(spot) for i in range(5)]
                    if (
                        self[lineup[-1]][1] == "r"
                        and lineup[-1] not in self.castle_x
                        and set([self[smid] for smid in lineup[1:-1]]) == {"empty"}
                    ):
                        if not any(
                            self.is_attacked(smid, plyother) for smid in lineup[:3]
                        ):
                            yield (spot, lineup[2])

    def make_move(self, fromto, ignore_promote=False):
        from_, to_, *promote = fromto

        plynow = {0: "w", 1: "b"}[len(self.history) % 2]
        pawn_dr = {"b": -1, "w": 1}[plynow]

        board = self._dupe()
        # make the move
        piece = board.piecemap[from_]
        k_spot = {"w": "e1", "b": "e8"}[plynow]
        if piece[1] == "k" and from_ == k_spot:
            # move rook for castling if moving 2 to left or right
            if to_[0] == "g":
                board.piecemap[f"f{to_[1]}"] = board.piecemap[f"h{to_[1]}"]
                del board.piecemap[f"h{to_[1]}"]
            if to_[0] == "c":
                board.piecemap[f"d{to_[1]}"] = board.piecemap[f"a{to_[1]}"]
                del board.piecemap[f"a{to_[1]}"]
        if piece[1] == "p" and board.enpassant and to_ == board.enpassant[0]:
            del board.piecemap[board.enpassant[1]]
        if not ignore_promote and piece[1] == "p" and to_[1] in "18":
            # pawn promotion
            piece = piece[0] + promote[0]
        board.piecemap[to_] = piece
        del board.piecemap[from_]
        # record enpassant history
        if (
            piece[1] == "p"
            and from_[1] == ("2" if plynow == "w" else "7")
            and to_ == Delta(0, pawn_dr * 2).from_(from_)
        ):
            board.enpassant = (Delta(0, pawn_dr).from_(from_), to_)
        else:
            board.enpassant = None
        # record castling history
        if from_ in Board.CASTLE_SPOTS and from_ not in self.castle_x:
            board.castle_x.add(from_)
        # record this move
        board.history.append(fromto)
        return board

    def interpret(self, who, pgn):
        moves = list(self.legal_moves())
        backrank = {"w": "1", "b": "8"}[who]

        if pgn == "O-O":
            # king side
            result = (f"e{backrank}", f"g{backrank}")
        elif pgn == "O-O-O":
            # queen side
            result = (f"e{backrank}", f"c{backrank}")
        else:
            m = re.match(
                "([RNBQK]|)([a-h]?[0-8]?)(x|)([a-h][1-8])(=[QRNB]|)([+!?]*)", pgn
            )

            if not m:
                raise InterpretationError(f"invalid pgn ply {pgn}")

            ptype = m.group(1)
            spot1 = m.group(2)  # possibly empty
            capture = m.group(3)
            spot2 = m.group(4)
            promotion = m.group(5)
            comment = m.group(6)

            if ptype == "":
                ptype = "p"
            else:
                ptype = ptype.lower()
            promotion = promotion[1].lower() if promotion else None

            potential = [
                spot for spot, piece in self._positions(who) if piece[1] == ptype
            ]

            if promotion:
                target = (spot2, promotion)
            else:
                target = (spot2,)
            matches = [(sp1, *target) for sp1 in potential if (sp1, *target) in moves]

            if spot1 != "":
                matches = [m for m in matches if spot1 in m[0]]

            if len(matches) == 1:
                result = matches[0]
            else:
                raise InterpretationError(f"there are {len(matches)}: {matches}")

        if result not in moves:
            raise InterpretationError(f"move {result} is not valid on this board")
        return result


def print_board(board):
    ranks = "87654321"
    files = "abcdefgh"
    cp = ChessPiece
    tcc = termcolor.colored
    for r in ranks:
        print(f"{r} ", end="")
        for f in files:
            index = ord(r) - ord("1") + ord(f) - ord("a")
            colors = {0: ("grey", "on_red"), 1: ("grey", "on_white")}[index % 2]
            # print(f"{f}{r}", end='')
            char = getattr(cp, board[f"{f}{r}"])
            print(tcc(f" {char} ", *colors), end="")
        print("\n", end="")
    print(f"   {'  '.join(files)}")


class PgnGame:
    def __init__(self, headlines, gamelines):
        self.game = " ".join(gamelines)
        self.headlines = headlines

    def plies(self):
        ply = 0
        game = self.game.split(" ")
        for token in game:
            if token.endswith("."):
                ply += 1
                assert ply == int(token[:-1])
                bw = "w"
            elif token in ("1-0", "0-1", "1/2-1/2"):
                yield (ply, "-", token)
            else:
                yield (ply, bw, token)
                bw = Board.other(bw)


def parse_pgn(fname):
    with open(fname, "r") as ff:
        lines = [ll.strip() for ll in ff]

    games = []
    headmode = None
    gamelines = []
    headlines = []
    for line in lines:
        if line.startswith("["):
            headmode = True
            headlines.append(line)
        elif line == "":
            if headmode == False:
                games.append(PgnGame(headlines, gamelines))
                headlines = []
                gamelines = []
                headmode = None
            elif headmode == True:
                headmode = False
        else:
            gamelines.append(line)
    return games


def play_pgn_game(game):
    print(game.headlines)
    # input("play game?  (enter)")
    board = Board.default_board()
    for ply in game.plies():
        print_board(board)

        if ply[1] == "-":
            print(f"game over: {ply[2]}")
            break
        print(ply)
        move = board.interpret(ply[1], ply[2])

        board = board.make_move(move)


def interactive_game(white_func, black_func):
    board = Board.default_board()
    while True:
        print_board(board)
        print(f"white:  {weight_board(board, 'w')}")
        print(f"black:  {weight_board(board, 'b')}")

        who = {"w": "white", "b": "black"}[board.who()]
        moves = list(board.legal_moves())
        if len(moves) == 0:
            other = {"w": "black", "b": "white"}[board.who()]
            if board.is_positional_check(board.who()):
                print(f"game over; {other} wins")
            else:
                print(f"game over; draw -- {who} has no legal moves")
            break
        elif len(board.piecemap) == 2:
            print("game over; draw -- 2 kings")
            break

        print(f"{who} to move; move #{len(board.history)//2+1}")

        func = {"w": white_func, "b": black_func}[board.who()]
        move = func(board)

        board = board.make_move(move)


def random_ai(board):
    import random
    import time

    time.sleep(2)

    moves = list(board.legal_moves())
    return random.choice(moves)


def deeplook(board, depth):
    for move in board.legal_moves():
        boar2 = board.make_move(move)
        if depth > 1:
            yield from deeplook(boar2, depth - 1)
        else:
            yield boar2


def spot_delta(sp1, sp2):
    return Delta(ord(sp1[0]) - ord(sp2[0]), ord(sp1[1]) - ord(sp2[1]))


def manhattan(delta):
    return abs(delta.df) + abs(delta.dr)


def mid_delta(sp):
    return min(manhattan(spot_delta(sp, center)) for center in ["d4", "d5", "e4", "e5"])


position_weights = {
    f"{f}{r}": 10 - mid_delta(f"{f}{r}") for f in "abcdefgh" for r in "12345678"
}


def weight_board(board, who):
    global position_weights
    return sum(position_weights[spot] for spot in board._attacked_positions(who))


def coverage_ai(board):
    who = board.who()
    other = Board.other(who)
    who_base = weight_board(board, who)
    best_results = {}
    for move in board.legal_moves():
        detail = []
        otherboard = board.make_move(move)
        other_base = weight_board(otherboard, other)
        for depth3 in deeplook(otherboard, 3):
            # maximize: (detail*[1] - who_base - (other_base - detail*[2]))
            who_depth, other_depth = weight_board(depth3, who), weight_board(
                depth3, other
            )
            detail.append(who_depth - who_base - (other_base - other_depth))
        best_results[move] = max(detail)

    return sorted(best_results.items(), key=lambda x: -x[1])[0][0]
    import random

    moves = list(board.legal_moves())
    return random.choice(moves)


def console_play(board):
    while True:
        pgn = input("Input move:  ")
        try:
            return board.interpret(board.who(), pgn)
        except InterpretationError as e:
            print(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument("--pgn", help="filename with pgn format games")
    parser.add_argument("--game", help="game index to play of pgn file")

    args = parser.parse_args()
    if args.pgn:
        games = parse_pgn(args.pgn)

        play_pgn_game(games[int(args.game) - 1])
    else:
        interactive_game(coverage_ai, console_play)
