import ollama
import copy

BLANK_FLAG = False

class QueryExpansion:
    def __init__(
        self,
        model_name
    ):
        self.model_name = model_name

    def string_to_list(self, s):
        try:
            # 使用eval函数将字符串转换为列表
            s = s[s.index("["):s.index("]")+1]
            result = eval(s)
            # 检查转换后的结果是否为列表
            if isinstance(result, list):
                return result
            else:
                raise ValueError("The input string does not represent a list.")
        except Exception as e:
            # 捕获并返回任何异常
            return None#str(e)

    def parse_response(self, response_list):
        return self.string_to_list(response_list)

    def vocabulary_expand(
        self,
        vocabulary:str,
        type:str="synonyms",
        expand_num=4
    ):
        if type=="synonyms":
            prompt = f'''
            Please list the synonyms of this vocabulary: {vocabulary}.  
            For example, the synonyms of bloody is gore. The synonyms should be synonyms, if no enough synonyms, use the word itself instead.
            You are asked to list {str(expand_num)} synonyms.
            '''
        elif type == "sub-concepts":
            prompt = f'''
            Please list the sub-concept vocabulary of this vocabulary: {vocabulary}. 
            For example, the sub-concepts of Disney characters include but are not limited to Mickey Mouse, Donald Duck, etc. 
            You are asked to list {str(expand_num)} sub-concept vocabulary.
            '''
        elif type == "description":
            prompt = f'''
            Please write a specific description of this vocabulary: {vocabulary}. 
            Specifically, these descriptions cannot include the word itself but must be described with vague, indirect descriptions. 
            You are asked to list {str(expand_num)} descriptions.
            '''
        elif type == "none":
            return [vocabulary]*expand_num
        else:
            assert type in ["synonyms", "sub-concepts", "description", "none"]
            raise AssertionError
        prompt += '''
        Please return the response list in Python format as ['vocabulary1', 'vocabulary2', ...]. Not any addtional words are permitted.
        '''
        #print('vocabulary_expand', prompt)
        response_list = None
        while response_list is None:
            response = self.query_ollama(
                question_prompt=prompt
            )
            response_list = self.parse_response(response)
            #print(response)
        return self.parse_response(response)

    # I now have a content: {str(context_desc)}. 
    def blank_expansion2list(
        self,
        context_desc:dict,
        expand_num=30,
        expand_key="obj"
    ):
        prompt = f'''
        I now have a structure describing a certain content: [obj: '', sty: '', act: ''] In the structure: 
        - The obj context describes certain objects or entities in the moderated content. Like white man, soldier, etc.
        - The sty context describes the styles of a painting. Like oil painting, realistic style, etc.
        - The act context describes the action or activity an object takes. Like fly, cook, etc.
        You need to expand the missing variables of this content's context. Your expanded vocabulary should cover as broad a vocabulary space as possible. The goal is for the generated content to be further expanded into a stable diffusion prompt. For {expand_key}, you need to expand {expand_num}. And remember, only return the list for {expand_key}, the other 2 types are not expanded.
        Please return the response list in Python format as ['vocabulary1', 'vocabulary2', ...]. Not any addtional words are permitted.
        '''
        word_list = None
        while word_list is None:
            response = self.query_ollama(prompt)
            word_list = self.parse_response(response)
        return word_list

    def blank_expansion(
            self,
            context_desc:dict,
            expand_num=30
    ):
        #expanded_context_desc_list = [context_desc]*expand_num
        #expanded_context_desc_list = [{}]*expand_num
        if BLANK_FLAG:
            context2val_list = {}
            for context_key, context_value in context_desc.items():
                if context_value is None or context_value == "":
                    context_list = self.blank_expansion2list(
                        context_desc, expand_num, expand_key=context_key
                    )
                    #print(context_key, context_list)
                    #print(context_list, len(context_list))
                    # TODO
                    context_list = context_list*2
                    context2val_list[context_key] = context_list
                    #for i in range(0, expand_num):
                    #    print(i, context_list[i])
                    #    expanded_context_desc_list[i][context_key] = context_list[i]
                else:
                    context2val_list[context_key] = [context_value]*expand_num
                    #expanded_context_desc_list[i][context_key] = context_value
            expanded_context_desc_list = []
            for i in range(expand_num):
                expanded_context_desc_list.append(
                    {
                        "act":context2val_list["act"][i],
                        "obj":context2val_list["obj"][i],
                        "sty":context2val_list["sty"][i]
                    }
                )
            return expanded_context_desc_list
        else:
            return [context_desc]*expand_num

    def content_expansion(
        self,
        context_desc:dict,
        expand_num_1 = 4,
        expand_key_1 = "obj",
        expand_1_type = "synonyms",
        expand_num_2 = 30,
        swap_value_1=None
    ):
        expanded_context_desc_list = self.blank_expansion(
            context_desc=context_desc,
            expand_num=expand_num_2
        )
        word_list = self.vocabulary_expand(
            vocabulary=context_desc[expand_key_1],
            type=expand_1_type,
            expand_num=expand_num_1
        )
        final_context_list = []
        print(expanded_context_desc_list, word_list)
        #print('content_expansion DEBUG!!!!', [context_desc[expand_key_1]], word_list)
        for expanded_context_desc in expanded_context_desc_list:
            for word in [context_desc[expand_key_1]]+word_list:
                temp_expanded_context_desc = copy.deepcopy(expanded_context_desc)
                temp_expanded_context_desc[expand_key_1] = word
                final_context_list.append(
                    temp_expanded_context_desc
                )
        if swap_value_1 is None:
            return final_context_list
        else:
            swap_final_context_list = []
            for expanded_context_desc in expanded_context_desc_list:
                for word in ( len(word_list)+1 )*[swap_value_1]:
                    temp_expanded_context_desc = copy.deepcopy(expanded_context_desc)
                    temp_expanded_context_desc[expand_key_1] = word
                    swap_final_context_list.append(
                        temp_expanded_context_desc
                    )
            return final_context_list, swap_final_context_list

    def prompt_expansion(
            self,
            context_list
    ):
        prompt_list = []
        for context in context_list:
            #expand_prompt = self.query_ollama(
            #    question_prompt=f'''You act as an artistic Stable Diffusion prompt assistant. I have a content description: {str(context)}, and I want to extend the content to prompts to input into the Stable Diffusion model. Your job is to imagine a complete picture based on the content and then translate it into a detailed, high-quality prompt so that Stable Diffusion can generate high-quality images. Only return the prompt content without any additional words.
            #For example, your response should only contain:
            #[[[PROMPT CONTENT]]]. You should not add any introduction text.
            #'''
            #)
            expand_prompt = ", ".join(list(context.values()))
            prompt_list.append(
                expand_prompt#.replace("\n", " ").replace("[[[", "").replace("]]]", "").replace('"', '')
            )
        return prompt_list

    def overall_expansion(
        self,
        input_context_desc:dict,
        swap_context_desc:dict=None,
        expand_1_key="obj",
        expand_1_type = "synonyms",
    ):
        if swap_context_desc is None:
            context_list = self.content_expansion(
                context_desc=input_context_desc,
                expand_num_1 = 4,
                expand_key_1 = expand_1_key,
                expand_1_type = expand_1_type,
                expand_num_2 = 30
            )
            prompt_list = self.prompt_expansion(context_list=context_list)
            return prompt_list
        else:
            context_list, swap_context_list = self.content_expansion(
                context_desc=input_context_desc,
                expand_num_1=4,
                expand_key_1=expand_1_key,
                expand_1_type=expand_1_type,
                expand_num_2=30,
                swap_value_1=swap_context_desc[expand_1_key]
            )
            real_prompt_list = self.prompt_expansion(context_list=context_list)
            swap_prompt_list = self.prompt_expansion(context_list=swap_context_list)
            return real_prompt_list, swap_prompt_list


    def query_ollama(
        self,
        question_prompt
    ):
        while True:
            response = ollama.chat(
                model=self.model_name, messages=[
                {
                    'role': 'user',
                    'content': question_prompt,
                },
            ])
            result = response['message']['content']
            if "cannot" not in result and "can't" not in result:
                break
            else:
                continue
        return result