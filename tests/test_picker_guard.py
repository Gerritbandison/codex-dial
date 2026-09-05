import unittest
from picker_guard import model_lists, same_list


def sample(names, spacing=29):
    rows=[]
    for index,name in enumerate(names,1):
        for word_index,word in enumerate(name.split(),1):
            rows.append(f'5\t1\t1\t1\t{index}\t{word_index}\t{790+(word_index-1)*70}\t{540+index*spacing}\t60\t14\t95\t{word}')
    return '\n'.join(rows)


class GuardTests(unittest.TestCase):
    def test_recognizes_multiple_aligned_model_choices(self):
        lists=model_lists(sample(['GPT-6 Astra','GPT-5.6 Sol','GPT-5.6 Terra','GPT-5.6 Luna']))
        self.assertTrue(lists)
        self.assertTrue(same_list(lists[0],lists[0]))

    def test_single_model_label_is_not_a_picker(self):
        self.assertEqual(model_lists(sample(['GPT-6 Astra'])),[])

    def test_distant_model_mentions_are_not_a_picker(self):
        self.assertEqual(model_lists(sample(['GPT-6 Astra','GPT-5.6 Sol','GPT-5.6 Terra'],spacing=120)),[])

    def test_empty_or_missing_list_cannot_confirm(self):
        self.assertEqual(model_lists(''),[])
        self.assertEqual(model_lists(sample(['ChatGPT hello','Nothing here','No picker'])),[])
