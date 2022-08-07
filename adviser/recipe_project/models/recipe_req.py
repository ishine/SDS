class RecipeReq:

    def __init__(self):

        self.ingredients    = []
        self.ease           = None
        self.rating         = None
        self.prep_time      = None
        self.cookbook       = None
        self.name           = None


    def from_informs(informs):
        req = RecipeReq()
        for slot, value in informs.items():
            vk = value.keys()
            if slot == 'ingredients':
                for ingredient in vk:
                    req.ingredients.append(ingredient)
            elif slot == 'name':
                req.name = vk[0]
            elif slot == 'ease':
                req.ease = vk[0]
            # multiple cookbooks?
            elif slot == 'cookbook':
                req.cookbook = vk[0]
            elif slot == 'prep_time':
                req.prep_time = vk[0]
            elif slot == 'rating':
                req.rating = vk[0]
            

        return req

    def is_empty(self):
        return (len(self.ingredients) == 0 
            and self.ease is None 
            and self.rating is None
            and self.prep_time is None
            and self.cookbook is None
            and self.name is None)
