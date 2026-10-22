import unittest
from decimal import Decimal
from venues.geometry import generate_block, coordinate, parse_csv, GeometryError, normalize_seat


class GeometryTests(unittest.TestCase):
    def test_straight_block_size_and_labels(self):
        result = generate_block(sector='A', rows=3, seats_per_row=4)
        self.assertEqual(len(result), 12)
        self.assertEqual(result[-1]['row'], '3')
        self.assertEqual(result[-1]['number'], '4')

    def test_coordinates_normalized(self):
        for seat in generate_block(sector='A'):
            self.assertTrue(0 <= seat['x'] <= 1 and 0 <= seat['y'] <= 1)
            self.assertEqual(seat['x'].as_tuple().exponent, -6)

    def test_arc_changes_middle(self):
        result = generate_block(sector='A', rows=1, seats_per_row=3, curve=.1)
        self.assertEqual(result[1]['y'] - result[0]['y'], Decimal('.100000'))

    def test_aisle_splits_adjacency(self):
        result = generate_block(sector='A', rows=1, seats_per_row=6, aisles_after=[3])
        self.assertNotEqual(result[2]['adjacency_group'], result[3]['adjacency_group'])
        self.assertEqual(result[3]['adjacency_position'], 0)

    def test_different_rows_have_different_groups(self):
        result = generate_block(sector='A', rows=2, seats_per_row=2)
        self.assertNotEqual(result[0]['adjacency_group'], result[2]['adjacency_group'])

    def test_odd_numbers(self):
        self.assertEqual([s['number'] for s in generate_block(sector='A',rows=1,seats_per_row=3,seat_step=2)], ['1','3','5'])

    def test_even_numbers(self):
        self.assertEqual([s['number'] for s in generate_block(sector='A',rows=1,seats_per_row=3,seat_start=2,seat_step=2)], ['2','4','6'])

    def test_reverse_numbers(self):
        self.assertEqual([s['number'] for s in generate_block(sector='A',rows=1,seats_per_row=3,seat_start=5,seat_step=-2)], ['5','3','1'])

    def test_reverse_alternate_rows(self):
        result=generate_block(sector='A', rows=2, seats_per_row=3, reverse_alternate=True)
        self.assertEqual([s['number'] for s in result[3:]], ['3','2','1'])

    def test_invalid_numbering(self):
        with self.assertRaises(GeometryError):
            generate_block(sector='A', seat_step=-1)

    def test_rotation(self):
        result=generate_block(sector='A', rows=1, seats_per_row=2, angle=90)
        self.assertEqual(result[0]['x'], result[1]['x'])
        self.assertGreater(result[1]['y'], result[0]['y'])

    def test_single_seat(self):
        result=generate_block(sector='A', rows=1, seats_per_row=1)
        self.assertEqual(len(result),1)

    def test_out_of_bounds_rejected(self):
        with self.assertRaises(GeometryError):generate_block(sector='A',x=.9,width=.5)

    def test_max_batch(self):
        with self.assertRaises(GeometryError):generate_block(sector='A',rows=100,seats_per_row=500)

    def test_infinite_coordinate(self):
        for value in ('NaN', 'Infinity', '-Infinity', '1.5', None):
            with self.subTest(value=value), self.assertRaises(GeometryError):coordinate(value)

    def test_unknown_fields_rejected(self):
        with self.assertRaises(GeometryError):normalize_seat({'sector':'A','row':'1','number':'1','x':.1,'y':.1,'price':10})

    def test_csv_comma(self):
        result=parse_csv('sector,row,number,x,y\nA,1,1,0.2,0.3\n')
        self.assertEqual(result[0]['x'], Decimal('.200000'))

    def test_csv_excel_separator(self):
        result=parse_csv('\ufeffsector;row;number;x;y\nA;1;1;0,2;0,3\n')
        self.assertEqual(result[0]['y'], Decimal('.300000'))

    def test_csv_quoted_label(self):
        result=parse_csv('sector,row,number,x,y\n"A, VIP",1,1,0.2,0.3\n')
        self.assertEqual(result[0]['sector'],'A, VIP')

    def test_csv_wrong_columns(self):
        with self.assertRaises(GeometryError):parse_csv('seat,x,y\n1,.2,.3')

    def test_csv_duplicate(self):
        with self.assertRaises(GeometryError):parse_csv('sector,row,number,x,y\nA,1,1,.2,.3\nA,1,1,.4,.5')

    def test_csv_empty(self):
        with self.assertRaises(GeometryError):parse_csv('sector,row,number,x,y\n')

    def test_csv_missing_coordinate(self):
        with self.assertRaises(GeometryError):parse_csv('sector,row,number,x,y\nA,1,1,.2\n')

    def test_csv_size_limit(self):
        with self.assertRaises(GeometryError):parse_csv('a'*524289)
