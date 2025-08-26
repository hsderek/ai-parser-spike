Input: an ndjson file with sample data, usually log or events but not always
Outputs
- VRL code to parse out useful data 
- A list of the fields extracted in JSON
  - their types based on out abstracted type model
  - Description of the field and useful information about it and whit it is useful and got parsed out
  - A simple parsing performance metric rating in terms of CPU cost
Options
- levels of parsing
    - High, medium an low levels for field paring selection. High is only the researched high value fields. Low is anything at all that could be considered of value.

Workflow - An API that will produce the following
Use the LLM (asking it to use use UP TO DATE knowledge - so current not at time of llm model build) to identify if this is a know data source
Use the LLM to spot fields in the JSON that should be parse out are potentially high value. Hard code to look for .msg .message and .description. This is for broad use cases such as cyber (syslog etc), travel (parsing out passports from PNR), iot, defence theatre battlespace, financial systems, etc.
Use the LLM to find broader sample data on the internet to create more variation
Then create faker data base on that for large volume testing
Use the LLM to find existing parsers that are out there already developed for those fields and collate the best options in a list to test with. Ideally MORE than one. 
Use the LLM to look on the internet for the most common names that should be used for the parsed fields leverage existing standards or commonly used tools and software. Then use those names  
Convert any regex or other inefficient mechanisms in those VRL parsers to more performant parsers
Test and iterate each parser until it works and produces the expected results
Test and iterate each parser until it is more performant using the large faker data set
Select the best parser
Iterate until we get that VRL as efficient as possible.


Constraints and Implementaiton
Don't implement the API in this spike project. Just code it so it will work well when implemented as a FAST API. Just a simple CLI. We need fast execution and debugging.
Always use and refer to VECTOR-VRL.md for all VRL work. It contains guidance to avoid common LLM mistakes.
Try to pre-tokenise the data and other techniques locally first to speed up LLM work, make it more efficient and to reduce cost
Code and optimise for the anthropic API
Assume the vector binary you will be testing with in already installed and is used for your testing cycle
We use an abstracted type model as defined in type_maps.csv. Ensure your returned results map the type of the data detected to the best type from the type column in that file
Alyways use uv and a project-local .venv
Create and update the appropriate gitignore and gitattributes for github deployment
Code so we can add progress and performance metrics for the API itself later on easily
Create a pytest framework that will allow you (claude code) to fast iterate and fix bugs in a tight loop
