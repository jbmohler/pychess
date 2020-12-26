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


class Delta:
    f2i = {c: ord(c) - ord("a") for c in "abcdefgh"}
    r2i = {c: ord(c) - ord("1") for c in "12345678"}
    i2f = {i: chr(i + ord("a")) for i in range(8)}
    i2r = {i: chr(i + ord("1")) for i in range(8)}

    def __init__(self, df, dr):
        self._t = (df, dr)

    def __mul__(self, mult):
        return Delta(self._t[0] * mult, self._t[1] * mult)

    def __repr__(self):
        return f"Delta{self._t}"

    def from_(self, spot):
        f, r = Delta.f2i[spot[0]], Delta.r2i[spot[1]]
        # assert 0 <= f < 8 and 0 <= r < 8
        f += self._t[0]
        r += self._t[1]
        if 0 <= f < 8 and 0 <= r < 8:
            return f"{Delta.i2f[f]}{Delta.i2r[r]}"
        else:
            raise IndexError(f"{spot} offset {self._t} is out of bounds")


class Board:
    CASTLE_SPOTS = ["a1", "e1", "h1", "a8", "e8", "h8"]

    def __init__(self, piecemap):
        self.piecemap = piecemap

        self.enpassant = None
        self.castle_x = set()
        self.history = []

    def _dupe(self):
        x = Board(self.piecemap.copy())
        x.enpassant = None
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
                        if self[spot2][0] == plyother or spot2 == self.enpassant:
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


def print_board(board):
    ranks = "87654321"
    files = "abcdefgh"
    cp = ChessPiece
    for r in ranks:
        print(f"{r} ", end="")
        for f in files:
            # print(f"{f}{r}", end='')
            print(getattr(cp, board[f"{f}{r}"]), end="")
        print("\n", end="")
    print(f"  {files}")


if __name__ == "__main__":
    board = Board.default_board()
    while True:
        print_board(board)

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

        print(f"{who} to move; move #{len(board.history)+1}")
        import time

        # time.sleep(.25)

        import random

        # for from_, to_ in board.legal_moves():
        #    print(from_, to_)
        move = random.choice(moves)

        board = board.make_move(move)
